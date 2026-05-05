import json
import logging
import os
from typing import Any, Dict, Optional
from urllib.parse import urlparse
import copy
import httpx
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
        # base_url comes from connection_data for the simple local deployment type
    elif provider == "vllm_fine_tuned":
        provider = "openai"
        cd["api_key"] = "EMPTY"
        if model_name and ":::" in model_name:
            # Test-connection path: form sends api_url:::model_path directly
            api_url, model_name = model_name.split(":::", 1)
            cd["base_url"] = f"{api_url}/v1"
        else:
            # Inference path: base_url and decrypted model_path stored in connection_data
            base_url = cd.pop("base_url", "")
            model_name = cd.pop("model_path", model_name)
            cd["base_url"] = f"{base_url}/v1"
        cd.pop("model", None)
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
        **cd,
        "model": model_name,
    }

    return init_chat_model(**model_kwargs)


@inject
class LLMProvider:

    def __init__(self):
        logger.info("LLMProvider initialized")

    async def get_configuration_definitions(
        self,
        auth_token: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ):
        """
        Get all LLM configurations
        """
        from app.core.config.settings import settings

        # Get fresh service instance to ensure correct tenant database session
        from app.dependencies.injector import injector
        fine_tuning_service = injector.get(OpenAIFineTuningService)
        successful_jobs = await fine_tuning_service.get_all_by_statuses([JobStatus.SUCCEEDED])

        # Transform successful jobs into options format
        fine_tuned_options = [
            {"value": job.fine_tuned_model, "label": "fine-tuned:" + job.suffix}
            for job in successful_jobs
        ]

        schemas = copy.deepcopy(LLM_FORM_SCHEMAS_DICT)

        # Inject OpenAI fine-tuned models into the openai schema
        if "openai" in schemas and "fields" in schemas["openai"]:
            for field in schemas["openai"]["fields"]:
                if field.get("name") == "model":
                    if "options" in field:
                        field["options"].extend(fine_tuned_options)
                    break

        # Inject running vLLM deployments into the vllm schema
        vllm_options = []
        if not settings.LOCAL_FINE_TUNE_API_URL:
            logger.warning("LOCAL_FINE_TUNE_API_URL not set — vLLM deployments will not appear as model options")
        else:
            _parsed_base = urlparse(settings.LOCAL_FINE_TUNE_API_URL)
            _base_scheme = _parsed_base.scheme or "http"
            _base_host = _parsed_base.hostname or "localhost"

            url = f"{settings.LOCAL_FINE_TUNE_API_URL.rstrip('/')}/api/v1/deployments"
            headers = {}
            if auth_token:
                headers["Authorization"] = f"Bearer {auth_token}"
            if tenant_id:
                headers["x-tenant-id"] = tenant_id
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    resp = await client.get(url, headers=headers)
                logger.info(f"vLLM deployment list: GET {url} → {resp.status_code}")
                if resp.status_code == 200:
                    all_deployments = resp.json()
                    logger.info(f"vLLM deployments returned: {len(all_deployments)}, statuses: {[d.get('status') for d in all_deployments]}")
                    for d in all_deployments:
                        if str(d.get("status", "")).lower() == "running":
                            model_path = d.get("model_path", "")
                            raw_api_url = d.get("api_url", "")
                            port = d.get("port", "")
                            # Use the deployment's api_url only when it points to a different host
                            # (model deployed on a different machine); otherwise build from settings host + port.
                            _parsed_api = urlparse(raw_api_url)
                            if raw_api_url and _parsed_api.hostname not in (None, "localhost", "127.0.0.1", _base_host):
                                api_url = raw_api_url.rstrip("/")
                            else:
                                api_url = f"{_base_scheme}://{_base_host}:{port}" if port else f"{_base_scheme}://{_base_host}"
                            label_name = model_path.split("/")[-1] if model_path else str(d.get("id", "unknown"))
                            vllm_options.append({
                                "value": f"{api_url}:::{model_path}",
                                "label": f"deployed: {label_name} (:{port})",
                            })
                else:
                    logger.warning(f"vLLM deployment list returned {resp.status_code} — check LOCAL_FINE_TUNE_SERVICE_TOKEN")
            except Exception as exc:
                logger.warning(f"Could not fetch vLLM deployments from {url}: {exc}")

        if "vllm_fine_tuned" in schemas and "fields" in schemas["vllm_fine_tuned"]:
            for field in schemas["vllm_fine_tuned"]["fields"]:
                if field.get("name") == "model":
                    field["options"] = vllm_options
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

        from app.core.data_residency import assert_provider_residency, bedrock_regions_from_connection_data
        from app.services.app_settings import AppSettingsService

        app_settings_service = injector.get(AppSettingsService)
        regions = bedrock_regions_from_connection_data(
            llm_provider.llm_model_provider,
            llm_provider.connection_data,
        )
        await assert_provider_residency(regions, app_settings_service)

        try:
            # Validate connection data
            validated_data = json.loads(
                json.dumps(llm_provider.connection_data)
            )  # clone the data

            validated_data.pop("masked_api_key", None)

            # Decrypt api_key for providers that need it
            original_provider = (llm_provider.llm_model_provider or "").lower()
            if original_provider not in ["vllm", "vllm_fine_tuned", "ollama"] and "api_key" in validated_data:
                validated_data["api_key"] = decrypt_key(validated_data["api_key"])

            if original_provider == "vllm_fine_tuned" and "model_path" in validated_data:
                validated_data["model_path"] = decrypt_key(validated_data["model_path"])

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
