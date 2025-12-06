import json
from typing import Dict, List
import os
import logging

from injector import inject
from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel

from app.core.utils.encryption_utils import decrypt_key
from app.core.utils.enums.open_ai_fine_tuning_enum import JobStatus
from app.db.models.llm import LlmProvidersModel
from app.services.llm_providers import LlmProviderService
from app.schemas.dynamic_form_schemas import LLM_FORM_SCHEMAS_DICT
from app.services.open_ai_fine_tuning import OpenAIFineTuningService


logger = logging.getLogger(__name__)


@inject
class LLMProvider:
    """Tenant-aware singleton class for managing LLM instances.

    Each tenant gets their own instance with isolated LLM configurations and cached models.
    This ensures that tenant-specific API keys, models, and configurations remain isolated.
    """

    llm_instances: Dict[str, BaseChatModel] = {}
    configurations: List[LlmProvidersModel] = []
    _loading: bool = False

    def __init__(
        self,
        llm_provider_service: LlmProviderService,
        fine_tuning_service: OpenAIFineTuningService,
    ):
        self.llm_instances = {}
        self.llm_provider_service = llm_provider_service
        self.fine_tuning_service = fine_tuning_service
        self.configurations = []
        self._loading = False
        logger.info("LLMProvider initialized")
        # Don't create background task that can conflict with request cleanup
        # Configurations will be loaded lazily when needed

    async def get_configuration_definitions(self):
        """
        Get all LLM configurations
        """
        successful_jobs = await self.fine_tuning_service.get_all_by_statuses([JobStatus.SUCCEEDED])

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

    async def reload(self) -> List[LlmProvidersModel]:
        """
        Get all LLM configurations

        Returns:
            List[LlmProvidersModel]: All LLM configurations
        """
        self.configurations = await self.llm_provider_service.get_all()
        self.llm_instances = {}
        return self.configurations

    def get_all_configurations(self) -> List[LlmProvidersModel]:
        """
        Get all LLM configurations

        Returns:
            List[LlmProvidersModel]: All LLM configurations
        """
        return self.configurations

    async def ensure_loaded(self):
        """
        Ensure configurations are loaded. Safe to call multiple times.
        """
        if not self.configurations and not self._loading:
            self._loading = True
            try:
                await self.reload()
            finally:
                self._loading = False

    def get_configuration(self, model_id: str) -> LlmProvidersModel:
        """
        Get an LLM configuration by its ID
        """
        default = next(
            (c for c in self.configurations if c.is_default == 1),
            self.configurations[0],
        )
        return next(
            (c for c in self.configurations if str(c.id) == str(model_id)), default
        )

    async def get_model(self, model_id: str | None = None) -> BaseChatModel:
        """
        Get an LLM instance by its ID

        Args:
            model_id: ID of the LLM instance to get

        Returns:
            BaseChatModel: The LLM instance

        Raises:
            ValueError: If no configuration exists for the given ID
        """
        # Ensure configurations are loaded
        await self.ensure_loaded()

        if model_id is None:
            model_id = str(self.configurations[0].id)
        if not model_id:
            raise ValueError("Model ID is required")
        model_id = str(model_id)

        if model_id not in self.llm_instances:
            # Find the configuration
            config = self.get_configuration(model_id)
            if not config:
                raise ValueError(f"No configuration found for model ID: {model_id}")

            try:
                # Validate connection data
                validated_data = json.loads(
                    json.dumps(config.connection_data)
                )  # clone the data

                validated_data.pop("masked_api_key", None)

                # Determine the actual provider to use
                provider = (config.llm_model_provider or "").lower()

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
                    and config.llm_model_provider
                    and config.llm_model_provider.lower() == "openai"
                ):
                    os.environ["OPENAI_API_KEY"] = validated_data["api_key"]
                    if validated_data.get("organization"):
                        os.environ["OPENAI_ORG_ID"] = validated_data["organization"]

                # Single unified flow for all providers
                model_kwargs = {
                    "model_provider": provider,
                    "model": config.llm_model,
                    **validated_data,
                }

                # Initialize the model
                llm = init_chat_model(**model_kwargs)

                self.llm_instances[model_id] = llm
                logger.info(f"Created new LLM instance with ID: {model_id}")
            except Exception as e:
                logger.error(f"Failed to initialize LLM instance: {str(e)}")
                raise

        return self.llm_instances[model_id]
