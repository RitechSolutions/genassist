import json
import logging
from typing import List

from langchain_core.messages import HumanMessage, SystemMessage

from app.core.utils.enums.conversation_topic_enum import ConversationTopic
from app.core.utils.enums.negative_conversation_reason import NegativeConversationReason
from app.modules.workflow.llm.provider import LLMProvider
from app.schemas.conversation_analysis import AnalysisResult
from app.schemas.conversation_transcript import TranscriptSegment
from app.schemas.llm import LlmAnalyst
from app.core.utils.bi_utils import clean_gpt_json_response


logger = logging.getLogger(__name__)


class GptKpiAnalyzer:

    async def analyze_transcript(
        self,
        transcript: str,
        llm_analyst: LlmAnalyst,
        max_attempts=3,
    ) -> AnalysisResult:
        """Analyze transcript using ChatGPT (LangChain) with retry on failure."""

        from app.dependencies.injector import injector

        llm_provider = injector.get(LLMProvider)
        llm = await llm_provider.get_model(llm_analyst.llm_provider_id)

        if (
            transcript is None
            or transcript.strip() == ""
            or len(transcript) == 0
            or transcript == "[]"
        ):
            raise ValueError("Transcript is empty! Nothing to analyze!")
        else:
            logger.debug(f"analyzing transcript: {transcript}")

        last_error_msg = ""
        last_response = ""
        user_prompt = ""

        for attempt in range(1, max_attempts + 1):
            try:
                # Modify prompt on retry attempts
                if attempt == 1:
                    user_prompt = self._create_user_prompt(transcript)
                else:
                    user_prompt = self._create_user_prompt(
                        transcript, error_hint=last_error_msg, attempt=attempt
                    )

                system_msg = SystemMessage(content=llm_analyst.prompt)
                user_msg = HumanMessage(content=user_prompt)

                response = await llm.ainvoke([system_msg, user_msg])
                response_text = response.content.strip()
                last_response = response_text

                summary_data = self._extract_summary_and_title(response_text)
                summary = summary_data.get("summary")
                title = summary_data.get("title")
                customer_speaker = summary_data.get("customer_speaker")
                metrics = self._extract_metrics(response_text)

                if (
                    summary
                    and title
                    and customer_speaker
                    and isinstance(metrics, dict)
                    and metrics
                ):
                    return AnalysisResult(
                        summary=summary,
                        title=title,
                        kpi_metrics=metrics,
                        customer_speaker=customer_speaker,
                    )

                raise ValueError("Parsing returned incomplete or invalid result.")

            except Exception as e:
                last_error_msg = str(e)
                logger.error(
                    f"Attempt {attempt}: Failed to parse GPT response as JSON. Error: {last_error_msg} - LastResponse: {last_response} - Prompt: {user_prompt}"
                )

        # raise AppException(error_key=ErrorKey.GPT_RETURNED_INCOMPLETE_RESULT)

    def _format_transcript(self, segments: List[TranscriptSegment]) -> str:
        """Format transcript segments into a readable string."""
        return "\n".join(
            f"Speaker {seg.speaker} ({seg.start_time:.2f}s - {seg.end_time:.2f}s):\n{seg.text}"
            for seg in segments
        )

    def _create_user_prompt(
        self, transcript_text: str, error_hint: str = None, attempt: int = 1
    ) -> str:
        """Create the analysis prompt for ChatGPT, optionally appending retry hints."""
        retry_instruction = ""
        if error_hint and attempt > 1:
            retry_instruction = f"""
            **Note:** This is attempt #{attempt}. The previous attempt failed with the following error:
            "{error_hint}"

            Please make sure your response strictly follows the requested format and especially corrects the issue that might have caused that error.
            """

        return f"""
            You are a customer experience expert. Please analyze this call center conversation transcript and provide 
            your response in the following format:

            **A) Title:**
            - Select the most appropriate title from the following list: {ConversationTopic.as_csv()}

            **B) Summary:**
            - Assess the operator's performance and whether the customer was satisfied
            - Identify key points of improvement

            **C) Identify the Customer:**
            - Indicate which speaker is the customer in this conversation with one word only (e.g., SPEAKER_00).

            **D) KPI Metrics, Tone, and Sentiment Analysis (JSON Format):**
            Provide the following KPI metrics, overall tone, and sentiment percentages as a JSON object:

            ```json
            {{
                "Response Time": (integer 0-10),
                "Customer Satisfaction": (integer 0-10),
                "Quality of Service": (integer 0-10),
                "Efficiency": (integer 0-10),
                "Resolution Rate": (integer 0-10),
                "Operator Knowledge": (integer 0-10),
                "Tone": "(choose one from: Hostile, Frustrated, Friendly, Polite, Neutral, Professional)",
                "Sentiment": {{
                    "positive": (float between 0-100),
                    "neutral": (float between 0-100),
                    "negative": (float between 0-100)
                }}
            }}
            ```

            Transcript:
            {transcript_text}

            Remember to maintain the exact format specified above. The JSON metrics should be integers between 0 and 10, 
            Tone must be one of the listed values, and sentiment percentages must sum up to 100%.

            {retry_instruction}
        """

    async def partial_hostility_analysis(
        self,
        transcript_segments: str,
        llm_analyst: LlmAnalyst,
    ) -> dict:

        from app.dependencies.injector import injector

        llm_provider = injector.get(LLMProvider)
        llm = await llm_provider.get_model(llm_analyst.llm_provider_id)

        # Create a short prompt for hostility detection
        # We'll ask for a JSON response with "sentiment" and "hostile_score"
        system_msg = SystemMessage(content=llm_analyst.prompt)

        user_prompt = f"""
        You are an impartial conversation analyst.

        Task:
        Analyse the following partial conversation transcript (a JSON list of messages).  
        Each message has:
        "text": "The content of the partial conversation transcript"
        "speaker": "The speaker, either customer or agent"
        "start_time": The moment the message started
        "end_time": The moment the message ended

        YOU MUST ALWAYS RETURN ONE JSON OBJECT WITH EXACTLY THREE KEYS:

         1. "hostile_score" between 0 and 100.
         2. "topic" string from this specific list: {ConversationTopic.as_csv()} based on the conversation 
         transcript. Return "Other" if none of the other topics match the conversation or if there isn't enough 
         context to decide.
         3. "negative_reason" string from this specific list: {NegativeConversationReason.as_csv()} based on the 
         conversation, if it is not negative, or if there isn't enough context to decide return "Other" for this field.

        ### Definition of hostility
        Hostility includes threats, insults, profanity, aggressive or intimidating tone, harassment, or hateful/discriminatory language.  
        Polite disagreement or calm criticism is **not** hostile.

        ### Hostile-score rubric
        | Range | Description & examples |
        |-------|------------------------|
        | 0-10  | Friendly, cooperative (“Thanks so much!”) |
        | 11-25 | Mild irritation, impatience (“Could you hurry?”) |
        | 26-50 | Frustrated or angry complaints, raised voice, light profanity (“This is ridiculous, fix it!”) |
        | 51-75 | Aggressive, repeated profanity, personal attacks (“You idiots never get it right.”) |
        | 76-90 | Threatening tone, explicit hostility (“If you don’t fix this I’ll report you.”) |
        | 91-100| Violent threats, hate speech (“I’ll ruin your business”, slurs) |

        Scoring instructions
        • Score the conversation as a whole (don’t average per-speaker).  
        • If hostility is mixed, choose the highest sustained level reached.  
        • Use whole numbers only (no decimals).

        ### Output rules
        • Think step-by-step internally but do not reveal your reasoning.  
        • Respond with JSON only, no prose, no comments, no trailing commas.  
        • Example:
        {{
            "topic": "Billing Questions",
            "hostile_score": 85,
            "negative_reason": "Bad Communication"
        }}

        Transcript:
        {transcript_segments}
        """
        logger.debug(f"User prompt for hostility:{user_prompt}")
        user_msg = HumanMessage(content=user_prompt)

        try:
            # Call the LLM synchronously in a background thread
            response = await llm.ainvoke([system_msg, user_msg])
            response_text = response.content.strip()

            # Remove json ticks
            response_text = clean_gpt_json_response(response_text)

            # Attempt to parse the JSON
            analysis_data = json.loads(response_text)
            logger.debug(f"Analysis data:{analysis_data}")

            # Basic validation
            if (
                "topic" in analysis_data
                and "hostile_score" in analysis_data
                and "negative_reason" in analysis_data
                and isinstance(analysis_data["hostile_score"], int)
            ):
                return analysis_data

            # If the JSON doesn't match the expected structure
            raise ValueError(
                "partial_hostility_analysis: Missing or invalid fields in JSON output."
            )

        except Exception as e:
            logger.warning(f"Hostility analysis failed: {e}")
            # Fallback to a safe default or re-raise
            return {"topic": "Other", "hostile_score": 0, "negative_reason": "Other"}

    def _extract_summary_and_title(self, text: str) -> dict:
        """Extract the title, summary, and customer speaker section from the response."""
        title_start = text.find("**A) Title:**")
        summary_start = text.find("**B) Summary:**")
        customer_start = text.find("**C) Identify the Customer:**")
        kpi_start = text.find("**D) KPI Metrics")

        raw_title = title = text[title_start + 13 : summary_start].strip()
        title = raw_title.lstrip("- ").strip()
        summary = text[summary_start + 15 : customer_start].strip()
        customer_speaker = text[customer_start + 32 : kpi_start].strip()
        return {
            "title": title,
            "summary": summary,
            "customer_speaker": customer_speaker,
        }

    def _extract_metrics(self, text: str) -> dict:
        """Extract and parse the KPI metrics JSON from the response."""
        json_start = text.find("{")
        json_end = text.rfind("}") + 1
        if json_start != -1 and json_end != -1:
            metrics_json = text[json_start:json_end]
            return json.loads(metrics_json)
        return {}
