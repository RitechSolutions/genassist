import json
import logging
import os
from typing import Any, Dict, Optional

from injector import inject
from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel

from app.core.utils.encryption_utils import decrypt_key
from app.core.utils.enums.open_ai_fine_tuning_enum import JobStatus
from app.schemas.dynamic_form_schemas import LLM_FORM_SCHEMAS_DICT
from app.services.llm_providers import LlmProviderService
from app.services.open_ai_fine_tuning import OpenAIFineTuningService

logger = logging.getLogger(__name__)


async def build_chat_model(
    provider_name: Optional[str],
    connection_data: Dict[str, Any],
    model_name: Optional[str],
) -> BaseChatModel:
    cd = dict(connection_data)
    original_provider = (provider_name or "").lower()
    provider = original_provider

    if provider == "vllm":
        provider = "openai"
        cd["api_key"] = "EMPTY"
    elif provider == "openrouter":
        provider = "openai"
        if "base_url" not in cd:
            cd["base_url"] = "https://openrouter.ai/api/v1"

    if provider == "openai" and original_provider == "openai":
        os.environ["OPENAI_API_KEY"] = cd.get("api_key", "")
        if cd.get("organization"):
            os.environ["OPENAI_ORG_ID"] = cd["organization"]

    model_kwargs = {
        "model_provider": provider,
        "model": model_name,
        **cd,
    }

    return init_chat_model(**model_kwargs)


@inject
class LLMProvider:

    def __init__(self):
        logger.info("LLMProvider initialized")

    async def get_configuration_definitions(self):
        """
        Get all LLM configurations
        """
        # Get fresh service instance to ensure correct tenant database session
        from app.dependencies.injector import injector
        fine_tuning_service = injector.get(OpenAIFineTuningService)
        successful_jobs = await fine_tuning_service.get_all_by_statuses([JobStatus.SUCCEEDED])

        # Transform successful jobs into options format
        fine_tuned_options = [
            {"value": job.fine_tuned_model, "label": "fine-tuned:" + job.suffix}
            for job in successful_jobs
        ]

        # Convert TypeSchema to dict for modification
        import copy

        schemas = copy.deepcopy(LLM_FORM_SCHEMAS_DICT)

        # Find the model field and add the fine-tuned options
        if "openai" in schemas and "fields" in schemas["openai"]:
            for field in schemas["openai"]["fields"]:
                if field.get("name") == "model":
                    # Add fine-tuned models to the existing options
                    if "options" in field:
                        field["options"].extend(fine_tuned_options)
                    break

        return schemas


    async def get_model(self, model_id: str | None = None) -> BaseChatModel:
        from app.dependencies.injector import injector
        llm_provider_service = injector.get(LlmProviderService)

        if model_id is None:
            all_providers = await llm_provider_service.get_all()

            llm_provider = all_providers[0] # default to the first provider
        else:
            llm_provider = await llm_provider_service.get_by_id(model_id)

        try:
            # Validate connection data
            validated_data = json.loads(
                json.dumps(llm_provider.connection_data)
            )  # clone the data

            validated_data.pop("masked_api_key", None)

            # Decrypt api_key for providers that need it
            original_provider = (llm_provider.llm_model_provider or "").lower()
            if original_provider not in ["vllm", "ollama"] and "api_key" in validated_data:
                validated_data["api_key"] = decrypt_key(validated_data["api_key"])

            llm = await build_chat_model(
                provider_name=llm_provider.llm_model_provider,
                connection_data=validated_data,
                model_name=llm_provider.llm_model,
            )
            logger.info(f"Created LLM with init_chat_model for llm provider with ID: {llm_provider.id}")
        except Exception as e:
            logger.error(f"Failed to initialize LLM instance: {str(e)}")
            raise

        return llm
