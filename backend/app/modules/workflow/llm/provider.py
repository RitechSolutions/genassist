from __future__ import annotations

import json
import logging
import os
from typing import TYPE_CHECKING, Any, Dict, Optional
from urllib.parse import urlparse
import copy
import httpx
from injector import inject
if TYPE_CHECKING:  # type hints only — langchain_core.language_models pulls torch/transformers
    from langchain_core.language_models import BaseChatModel
from app.core.config.llm_prompt_cache_capabilities import bedrock_cache_family
from app.core.utils.encryption_utils import decrypt_key
from app.core.utils.enums.open_ai_fine_tuning_enum import JobStatus
from app.core.utils.enums.bedrock_fine_tuning_enum import (
    BedrockDeploymentStatus,
    BedrockJobStatus,
)
from app.schemas.dynamic_form_schemas import LLM_FORM_SCHEMAS_DICT
from app.services.llm_providers import LlmProviderService
from app.services.open_ai_fine_tuning import OpenAIFineTuningService
from app.services.bedrock_fine_tuning import BedrockFineTuningService

logger = logging.getLogger(__name__)

def _bedrock_supports_prompt_caching(model_name: Optional[str]) -> bool:
    """True if this Bedrock model accepts prompt caching"""
    if bedrock_cache_family(model_name) is not None:
        return True
    logger.debug("Prompt caching skipped: %r is not a cache-capable Bedrock model", model_name)
    return False


async def build_chat_model(
    provider_name: Optional[str],
    connection_data: Dict[str, Any],
    model_name: Optional[str],
    prompt_caching_enabled: bool = False,
) -> BaseChatModel:
    cd = dict(connection_data)
    original_provider = (provider_name or "").lower()
    provider = original_provider

    # Bedrock ARN model ids (custom / fine-tuned / provisioned / inference-profile) don't
    # encode their foundation-model family, so langchain_aws requires an explicit
    # `provider`. Pull the user-selected family out of connection_data here so it never
    # collides with init_chat_model's own `model_provider` routing kwarg in the spread below.
    bedrock_model_provider = cd.pop("model_provider", None)

    cd.pop("prompt_caching_enabled", None)

    if provider == "vllm":
        provider = "openai"
        cd["api_key"] = "EMPTY"
        # base_url comes from connection_data for the simple local deployment type
    elif provider == "vllm_fine_tuned":
        provider = "openai"
        cd["api_key"] = "EMPTY"
        # connection_data.model always holds the api_url:::model_path value
        raw = cd.pop("model", model_name) or model_name
        if ":::" in raw:
            api_url, model_name = raw.split(":::", 1)
            cd["base_url"] = f"{api_url}/v1"
    elif provider == "openrouter":
        provider = "openai"
        if "base_url" not in cd:
            cd["base_url"] = "https://openrouter.ai/api/v1"
    elif provider == "bedrock":
        if cd.pop("reasoning_enabled", False):
            effort = cd.pop("reasoning_effort", "low")
            extra_fields = dict(cd.get("additional_model_request_fields") or {})
            extra_fields["reasoningConfig"] = {"type": "enabled", "maxReasoningEffort": effort}
            cd["additional_model_request_fields"] = extra_fields
        else:
            cd.pop("reasoning_effort", None)
        # Use the Converse API instead of the legacy InvokeModel path so inference params
        # (max_tokens, temperature) are normalized into inferenceConfig across model
        # families. Nova rejects a top-level max_tokens on InvokeModel; Converse handles
        # it, and it's AWS's recommended API for Nova/Claude/Llama/custom models alike.
        provider = "bedrock_converse"
    elif provider == "anthropic":
        if cd.pop("thinking_enabled", False):
            cd["thinking"] = {"type": "enabled", "budget_tokens": cd.pop("thinking_budget_tokens", 2000)}
            cd["temperature"] = 1  # Anthropic requires temperature=1 when thinking is enabled
        else:
            cd.pop("thinking_budget_tokens", None)
    elif provider == "openai":
        if not cd.get("reasoning_effort"):
            cd.pop("reasoning_effort", None)

    if provider == "openai" and original_provider == "openai":
        os.environ["OPENAI_API_KEY"] = cd.get("api_key", "")
        if cd.get("organization"):
            os.environ["OPENAI_ORG_ID"] = cd["organization"]

    model_kwargs = {
        "model_provider": provider,
        **cd,
        "model": model_name,
    }

    # A full ARN needs the foundation-model family passed through to ChatBedrockConverse
    # as `provider`; plain base model ids infer it themselves and must not receive it.
    if original_provider == "bedrock" and isinstance(model_name, str) and model_name.startswith("arn:"):
        if not bedrock_model_provider:
            raise ValueError(
                "Select a Model Provider (e.g. amazon, anthropic) when using a Bedrock model ARN."
            )
        model_kwargs["provider"] = bedrock_model_provider

    # Native Opik LLM tracing: attach the OpikTracer callback at construction so every
    # invocation of this model (including nested agent loops) is traced. No-op unless
    # USE_OPIK is enabled.
    from app.modules.workflow.llm.opik_tracing import get_opik_callbacks

    callbacks = get_opik_callbacks()
    if callbacks:
        model_kwargs["callbacks"] = callbacks

    # Imported here, not at module top level: langchain.chat_models transitively pulls
    # torch/transformers, which must not be loaded into a Celery prefork master process.
    from langchain.chat_models import init_chat_model

    llm = init_chat_model(**model_kwargs)

    # Wrap outside init_chat_model so the Opik callbacks stay attached to the inner
    # model and every invocation is still traced.
    if prompt_caching_enabled and (
        provider == "anthropic"
        or (provider == "bedrock_converse" and _bedrock_supports_prompt_caching(model_name))
    ):
        from app.modules.workflow.llm.prompt_caching_chat_model import PromptCachingChatModel

        return PromptCachingChatModel(inner=llm, cache_style=provider)

    return llm


async def _apply_model_catalog(schemas: Dict[str, Any]) -> None:
    """Append the tenant's registered models to each provider's ``model`` options.

    Purely additive: ``LLM_FORM_SCHEMAS`` stays the source of truth, so an empty
    catalog leaves ``schemas`` exactly as the built-in definitions produced it.
    Failures are swallowed — the LLM provider form must never break because the
    catalog could not be read.
    """
    try:
        from app.dependencies.injector import injector
        from app.services.llm_model_catalog import LlmModelCatalogService

        overlay = await injector.get(LlmModelCatalogService).build_option_overlay()
    except Exception as exc:
        logger.warning(
            "Could not read the LLM model catalog; serving built-in models only: %s", exc
        )
        return

    for provider_key, extra_options in overlay.items():
        schema = schemas.get(provider_key)
        if not schema or "fields" not in schema:
            continue
        for field in schema["fields"]:
            if field.get("name") != "model":
                continue
            existing = field.get("options") or []
            seen = {opt.get("value") for opt in existing}
            field["options"] = [
                *existing,
                *(opt for opt in extra_options if opt["value"] not in seen),
            ]
            break


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

        # Deployed Bedrock (Nova) custom models — only those with a deployment ARN are
        # invokable, so surface those as suggestions on the bedrock model field.
        bedrock_service = injector.get(BedrockFineTuningService)
        bedrock_completed = await bedrock_service.get_all_by_statuses([BedrockJobStatus.COMPLETED])
        bedrock_options = [
            {"value": job.deployment_arn, "label": "fine-tuned:" + (job.suffix or job.custom_model_name)}
            for job in bedrock_completed
            if job.deployment_arn
            and job.deployment_status == BedrockDeploymentStatus.ACTIVE
        ]

        schemas = copy.deepcopy(LLM_FORM_SCHEMAS_DICT)

        # Inject OpenAI fine-tuned models into the openai schema
        if "openai" in schemas and "fields" in schemas["openai"]:
            for field in schemas["openai"]["fields"]:
                if field.get("name") == "model":
                    if "options" in field:
                        field["options"].extend(fine_tuned_options)
                    break

        # Inject deployed Bedrock fine-tuned models as suggestions on the bedrock model
        # field. The field stays free-text (type="text"); the frontend renders a datalist
        # so a user can pick a deployed model ARN or type any base model id.
        if bedrock_options and "bedrock" in schemas and "fields" in schemas["bedrock"]:
            for field in schemas["bedrock"]["fields"]:
                if field.get("name") == "model":
                    field["options"] = [*(field.get("options") or []), *bedrock_options]
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

        # Tenant-registered models, appended last so the built-in lists keep their
        # order and win on any collision.
        await _apply_model_catalog(schemas)

        return schemas


    async def get_model(
        self,
        model_id: str | None = None,
        prompt_caching_enabled: bool = False,
    ) -> BaseChatModel:
        from app.dependencies.injector import injector
        llm_provider_service = injector.get(LlmProviderService)

        if model_id is None:
            all_providers = await llm_provider_service.get_all()

            llm_provider = all_providers[0] # default to the first provider
        else:
            llm_provider = await llm_provider_service.get_by_id(model_id)

        return await self._build_from_provider(llm_provider, prompt_caching_enabled)

    async def _build_one(self, model_id: str, prompt_caching_enabled: bool = False) -> BaseChatModel:
        """Build a single chat model from a stored provider id.

        Shared by get_model and get_model_with_fallback so residency checks,
        decryption, and init_chat_model stay in one place.
        """
        from app.dependencies.injector import injector
        llm_provider_service = injector.get(LlmProviderService)

        llm_provider = await llm_provider_service.get_by_id(model_id)
        return await self._build_from_provider(llm_provider, prompt_caching_enabled)

    async def _build_from_provider(self, llm_provider, prompt_caching_enabled: bool = False) -> BaseChatModel:
        from app.dependencies.injector import injector
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


            llm = await build_chat_model(
                provider_name=llm_provider.llm_model_provider,
                connection_data=validated_data,
                model_name=llm_provider.llm_model,
                prompt_caching_enabled=prompt_caching_enabled,
            )
            logger.info(f"Created LLM with init_chat_model for llm provider with ID: {llm_provider.id}")
        except Exception as e:
            logger.error(f"Failed to initialize LLM instance: {str(e)}")
            raise

        return llm

    async def get_model_for_node(
        self,
        provider_id: str | None,
        fallback_chain_id: str | None = None,
        prompt_caching_enabled: bool = False,
    ) -> BaseChatModel:
        """Resolve the model a node should use, honoring an optional fallback chain.

        Without a chain this behaves exactly like get_model(provider_id). With a
        chain, the node's own provider stays the primary (highest priority) and the
        chain's providers are appended as ordered fallbacks; the chain's retry policy
        is applied per provider.
        """
        if not fallback_chain_id:
            return await self.get_model(provider_id, prompt_caching_enabled)

        from app.dependencies.injector import injector
        from app.services.fallback_chains import FallbackChainService

        chain = await injector.get(FallbackChainService).get_by_id(fallback_chain_id)

        chain_ids = [str(pid) for pid in (chain.provider_ids or []) if pid]
        if provider_id:
            effective_ids = [str(provider_id)] + [pid for pid in chain_ids if pid != str(provider_id)]
        else:
            effective_ids = chain_ids

        retry_policy = chain.retry_policy.model_dump() if chain.retry_policy else None
        return await self.get_model_with_fallback(effective_ids, retry_policy, prompt_caching_enabled)

    async def get_model_with_fallback(
        self,
        provider_ids: list[str],
        retry_policy: Optional[Dict[str, Any]] = None,
        prompt_caching_enabled: bool = False,
    ) -> BaseChatModel:
        """Build a chat model that fails over across an ordered list of providers.

        Each provider is built via _build_one and wrapped with per-model retry
        (exponential backoff). The list is composed into a FallbackChatModel that
        tries each provider in order on transient errors. When there is a single
        provider and no retry policy, the bare model is returned unchanged so
        existing single-provider nodes behave exactly as before.

        Args:
            provider_ids: Ordered provider ids; index 0 is the primary.
            retry_policy: Optional dict with ``retry_count``, ``backoff_seconds``,
                a default ``timeout_seconds``, and a per-provider
                ``provider_timeouts`` map ``{provider_id: seconds}`` that overrides
                the default for specific providers.
        """
        ids = [pid for pid in (provider_ids or []) if pid]
        if not ids:
            raise ValueError("get_model_with_fallback requires at least one provider id")

        retry_count = int((retry_policy or {}).get("retry_count", 0) or 0)
        backoff_seconds = float((retry_policy or {}).get("backoff_seconds", 0) or 0)
        default_timeout = float((retry_policy or {}).get("timeout_seconds", 0) or 0)
        provider_timeouts = (retry_policy or {}).get("provider_timeouts") or {}

        def _timeout_for(pid: str) -> float:
            # Per-provider override falls back to the chain default (0 = no limit).
            raw = provider_timeouts.get(pid, default_timeout)
            try:
                return float(raw or 0)
            except (TypeError, ValueError):
                return 0.0

        has_retry = retry_count > 0
        has_timeout = default_timeout > 0 or any(_timeout_for(pid) > 0 for pid in ids)

        # Fast path: single provider, no retries, no timeout → no wrapper, zero
        # behavior change for plain single-provider nodes.
        if len(ids) == 1 and not has_retry and not has_timeout:
            return await self._build_one(ids[0], prompt_caching_enabled)

        from app.modules.workflow.llm.fallback_chat_model import FallbackChatModel

        children: list[Any] = []
        kept_ids: list[str] = []
        for pid in ids:
            try:
                # Children stay as raw chat models (NOT wrapped with .with_retry, which
                # returns a RunnableRetry lacking bind_tools and would break the agent
                # path). Per-provider retry is handled inside FallbackChatModel instead.
                model = await self._build_one(pid, prompt_caching_enabled)
            except Exception as e:
                # A provider that can't even be instantiated (e.g. deleted) is skipped
                # so the rest of the chain can still serve the request.
                logger.exception(f"Skipping fallback provider {pid}: failed to build ({e})")
                continue
            children.append(model)
            kept_ids.append(pid)

        if not children:
            raise ValueError("get_model_with_fallback: no providers could be built")

        return FallbackChatModel(
            models=children,
            provider_ids=kept_ids,
            retry_count=retry_count,
            retry_backoff_seconds=backoff_seconds,
            request_timeouts=[_timeout_for(pid) for pid in kept_ids],
        )
