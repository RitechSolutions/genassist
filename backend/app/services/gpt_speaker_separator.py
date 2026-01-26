import json
import logging

from langchain_core.messages import HumanMessage, SystemMessage

from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.schemas.llm import LlmAnalyst
from app.core.utils.bi_utils import clean_gpt_json_response
from app.modules.workflow.llm.provider import LLMProvider


logger = logging.getLogger(__name__)


class SpeakerSeparator:

    def _build_user_prompt(
        self, transcribed_text: str, attempt: int = 1, error_hint: str = ""
    ) -> str:
        """Create a user prompt with retry explanation included on subsequent attempts."""
        retry_instruction = ""
        if attempt > 1 and error_hint:
            retry_instruction = f"""
                Note: This is attempt #{attempt}. The previous response failed to parse as JSON. The error was:
                \"{error_hint}\"

                Please make sure the response is a clean JSON array, not wrapped in Markdown or backticks, and that each object in the array contains 'text', 'speaker', and 'start_time' fields as required.
            """

        return f"""Here is a transcribed conversation as JSON:\n\n{transcribed_text}\n\n
            If your response is not valid JSON, it may cause a system error.
            {retry_instruction}
            Ensure your response is a **pure JSON array** without Markdown formatting like triple backticks or labels like 'json'.
        """

    async def separate(
        self, transcribed_text: str, llm_analyst: LlmAnalyst, max_retries: int = 3
    ) -> list[dict]:
        """
        Calls an LLM to split a transcribed conversation into structured speaker-labeled sentences.
        Gets the system prompt and model name/type from the analyst config.
        Retries on JSON parsing errors.
        """
        from app.dependencies.injector import injector

        llm_provider = injector.get(LLMProvider)
        llm = await llm_provider.get_model(llm_analyst.llm_provider_id)

        last_error_msg = ""

        for attempt in range(1, max_retries + 1):
            user_prompt = self._build_user_prompt(
                transcribed_text, attempt=attempt, error_hint=last_error_msg
            )

            try:
                response = await llm.ainvoke(
                    [
                        SystemMessage(content=llm_analyst.prompt),
                        HumanMessage(content=user_prompt),
                    ],
                )
                response_text = clean_gpt_json_response(response.content)
                structured_conversation = json.loads(response_text)

                if isinstance(structured_conversation, list) and all(
                    isinstance(item, dict) for item in structured_conversation
                ):
                    return structured_conversation
                else:
                    logger.warning(f"Attempt {attempt}: Unexpected JSON structure.")

            except json.JSONDecodeError as e:
                last_error_msg = str(e)
                logger.error(
                    f"Attempt {attempt}: Failed to parse GPT response as JSON. Error: {last_error_msg}"
                )

        raise AppException(error_key=ErrorKey.GPT_FAILED_JSON_PARSING)
