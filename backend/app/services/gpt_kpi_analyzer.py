import json
import logging
from typing import List
import asyncio
from langchain.schema import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
<<<<<<< HEAD

from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
=======
from app.core.utils.encryption_utils import decrypt_key
>>>>>>> development
from app.schemas.conversation_analysis import AnalysisResult
from app.schemas.conversation_transcript import TranscriptSegment
from app.schemas.llm import LlmAnalyst
from app.core.utils.bi_utils import clean_gpt_json_response
from langchain_anthropic import ChatAnthropic
<<<<<<< HEAD
from app.core.config.settings import settings
=======
>>>>>>> development
logger = logging.getLogger(__name__)


class GptKpiAnalyzer:
<<<<<<< HEAD
    def __init__(self, model_name=settings.DEFAULT_OPEN_AI_GPT_MODEL, temperature=0):
        self.model_name = model_name
        self.temperature = temperature
        self.llm = ChatOpenAI(model=model_name, temperature=temperature)
=======
>>>>>>> development

    def _switch_model(self, llm_analyst: LlmAnalyst):
        """Switch the active LLM model and library based on provider."""
        logger.info(f"Using LLM {llm_analyst.llm_provider.llm_model_provider} model: {llm_analyst.llm_provider.llm_model}")

        api_key = decrypt_key(llm_analyst.llm_provider.connection_data.get("api_key"))

        if llm_analyst.llm_provider.llm_model_provider.lower() == "anthropic":
            self.llm = ChatAnthropic(model_name=llm_analyst.llm_provider.llm_model,
                                     temperature=llm_analyst.llm_provider.connection_data.get("temperature", 0),
                                     api_key=api_key)
        else:
            self.llm = ChatOpenAI(model=llm_analyst.llm_provider.llm_model,
                                  temperature=llm_analyst.llm_provider.connection_data.get("temperature", 0),
                                  api_key=api_key)


    async def analyze_transcript(
            self,
            transcript: str,
            llm_analyst: LlmAnalyst,
            max_attempts=3,
            ) -> AnalysisResult:
        """Analyze transcript using ChatGPT (LangChain) with retry on failure."""

        self._switch_model(llm_analyst)

        if transcript is None or transcript.strip() == "" or len(transcript) == 0 or transcript == "[]":
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
                    user_prompt = self._create_user_prompt(transcript, error_hint=last_error_msg,
                                                           attempt=attempt)

                system_msg = SystemMessage(content=llm_analyst.prompt)
                user_msg = HumanMessage(content=user_prompt)

                response = await asyncio.to_thread(
                    self.llm.invoke,
                    [system_msg, user_msg]
                )
                response_text = response.content.strip()
                last_response = response_text

                summary_data = self._extract_summary_and_title(response_text)
                summary = summary_data.get("summary")
                title = summary_data.get("title")
                customer_speaker = summary_data.get("customer_speaker")
                metrics = self._extract_metrics(response_text)

                if summary and title and customer_speaker and isinstance(metrics, dict) and metrics:
                    return AnalysisResult(
                            summary=summary,
                            title=title,
                            kpi_metrics=metrics,
                            customer_speaker=customer_speaker
                            )

                raise ValueError("Parsing returned incomplete or invalid result.")

            except Exception as e:
                last_error_msg = str(e)
                logger.error(f"Attempt {attempt}: Failed to parse GPT response as JSON. Error: {last_error_msg} - LastResponse: {last_response} - Prompt: {user_prompt}")

        #raise AppException(error_key=ErrorKey.GPT_RETURNED_INCOMPLETE_RESULT)


    def _format_transcript(self, segments: List[TranscriptSegment]) -> str:
        """Format transcript segments into a readable string."""
        return "\n".join(
            f"Speaker {seg.speaker} ({seg.start_time:.2f}s - {seg.end_time:.2f}s):\n{seg.text}"
            for seg in segments
        )


    def _create_user_prompt(self, transcript_text: str, error_hint: str = None, attempt: int = 1) -> str:
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
            - Select the most appropriate title from the following list: Product Inquiry, Technical Support, Billing Questions, Other

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
        """
        Given a list of partial transcript segments, analyze the text to determine a "hostility_score"
        between 0 and 100, plus a top-level sentiment string (e.g., negative/positive/neutral).

        Returns a dict like:
        {
            "sentiment": "negative",
            "hostile_score": 85
        }
        """

        self._switch_model(llm_analyst)

        # Create a short prompt for hostility detection
        # We'll ask for a JSON response with "sentiment" and "hostile_score"
        system_msg = SystemMessage(
            content=llm_analyst.prompt
        )

        user_prompt = f"""
        Analyze the following partial conversation transcript which is a json object.
        The fields of the json list are:
                            
        "text": "The content of the partial conversation transcript"
        "speaker": "The speaker, either customer or agent"
        "start_time": The moment the message started
        "end_time": The moment the message ended
  
        Return a single JSON object
        with two fields:
        1) "sentiment" = one of "negative", "neutral", or "positive"
        2) "hostile_score" = an integer from 0 to 100 representing how hostile the conversation is so far.

        Transcript:
        {transcript_segments}

        Return ONLY valid JSON without additional commentary.
        Example:
        {{
          "sentiment": "negative",
          "hostile_score": 65
        }}
        """

        user_msg = HumanMessage(content=user_prompt)

        try:
            # Call the LLM synchronously in a background thread
            response = await asyncio.to_thread(self.llm.invoke, [system_msg, user_msg])
            response_text = response.content.strip()

            # Remove json ticks
            response_text = clean_gpt_json_response(response_text)

            # Attempt to parse the JSON
            analysis_data = json.loads(response_text)

            # Basic validation
            if (
                "sentiment" in analysis_data
                and "hostile_score" in analysis_data
                and isinstance(analysis_data["hostile_score"], int)
            ):
                return analysis_data

            # If the JSON doesn't match the expected structure
            raise ValueError("partial_hostility_analysis: Missing or invalid fields in JSON output.")

        except Exception as e:
            logger.warning(f"Hostility analysis failed: {e}")
            # Fallback to a safe default or re-raise
            return {
                "sentiment": "neutral",
                "hostile_score": 0
            }



    def _extract_summary_and_title(self, text: str) -> dict:
        """Extract the title, summary, and customer speaker section from the response."""
        title_start = text.find("**A) Title:**")
        summary_start = text.find("**B) Summary:**")
        customer_start = text.find("**C) Identify the Customer:**")
        kpi_start = text.find("**D) KPI Metrics")

        raw_title = title = text[title_start + 13:summary_start].strip()
        title = raw_title.lstrip("- ").strip()
        summary = text[summary_start + 15:customer_start].strip()
        customer_speaker = text[customer_start + 32:kpi_start].strip()
        return {"title": title, "summary": summary, "customer_speaker": customer_speaker}


    def _extract_metrics(self, text: str) -> dict:
        """Extract and parse the KPI metrics JSON from the response."""
        json_start = text.find("{")
        json_end = text.rfind("}") + 1
        if json_start != -1 and json_end != -1:
            metrics_json = text[json_start:json_end]
            return json.loads(metrics_json)
        return {}

