import json
import os
import logging
from injector import inject
from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel
from app.core.utils.encryption_utils import decrypt_key
from app.core.utils.enums.open_ai_fine_tuning_enum import JobStatus
from app.services.llm_providers import LlmProviderService
from app.schemas.dynamic_form_schemas import LLM_FORM_SCHEMAS_DICT
from app.services.open_ai_fine_tuning import OpenAIFineTuningService


logger = logging.getLogger(__name__)


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

            # Determine the actual provider to use
            provider = (llm_provider.llm_model_provider or "").lower()

            # Handle vLLM (uses OpenAI-compatible API)
            if provider == "vllm":
                provider = "openai"  # Translate vLLM to OpenAI provider
                validated_data["api_key"] = "EMPTY"  # vLLM doesn't need auth

            # Handle API key decryption for providers that need it
            elif "api_key" in validated_data and provider not in ["ollama"]:
                validated_data["api_key"] = decrypt_key(validated_data["api_key"])

            # Set up environment variables if needed
            if (
                provider == "openai"
                and llm_provider.llm_model_provider
                and llm_provider.llm_model_provider.lower() == "openai"
            ):
                os.environ["OPENAI_API_KEY"] = validated_data["api_key"]
                if validated_data.get("organization"):
                    os.environ["OPENAI_ORG_ID"] = validated_data["organization"]

            # Single unified flow for all providers
            model_kwargs = {
                "model_provider": provider,
                "model": llm_provider.llm_model,
                **validated_data,
            }

            # Initialize the model
            llm = init_chat_model(**model_kwargs)
            logger.info(f"Created LLM with init_chat_model for llm provider with ID: {llm_provider.id}")
        except Exception as e:
            logger.error(f"Failed to initialize LLM instance: {str(e)}")
            raise

        return llm
