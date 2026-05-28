import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import httpx
import jwt
from injector import inject
from starlette_context import context

from app.core.config.settings import settings
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException, UpstreamServiceError
from app.core.tenant_scope import get_tenant_context
from app.schemas.local_fine_tuning import (
    CreateDeploymentRequest,
    CreateLocalFineTuneJobRequest,
    DeleteJobFilesRequest,
    DeleteJobFilesResponse,
    DeploymentStopResponse,
    LocalFineTuneDeployment,
    LocalFineTuneDeploymentHealth,
    LocalFineTuneJob,
    LocalFineTuneJobEvent,
    LocalFineTuneSupportedModel,
    SystemGpusResponse,
    TestInferenceResponse,
)

logger = logging.getLogger(__name__)


@inject
class LocalFineTuningService:
    """Proxy service that forwards local fine-tuning API calls to the external service.

    A short-lived service-to-service JWT is minted per request, signed with the
    shared secret in ``settings.LOCAL_FINE_TUNE_JWT_SECRET`` (HS256), and sent as
    a Bearer token. The payload carries ``tenant_id`` (so the upstream can
    derive the tenant) and ``origin`` from ``settings.LOCAL_FINE_TUNING_CALL_ORIGIN``
    (so the upstream knows which calling environment it's serving).
    """

    _TOKEN_ALGORITHM = "HS256"
    _TOKEN_TTL_SECONDS = 300

    def __init__(self):
        logger.info("LocalFineTuningService initialized")

    def _base_url(self) -> str:
        if not settings.LOCAL_FINE_TUNE_API_URL:
            raise AppException(
                error_key=ErrorKey.INTERNAL_ERROR,
                status_code=503,
                error_detail="LOCAL_FINE_TUNE_API_URL not configured",
            )
        return settings.LOCAL_FINE_TUNE_API_URL.rstrip("/")

    def _mint_token(self) -> str:
        if not settings.LOCAL_FINE_TUNE_JWT_SECRET:
            raise AppException(
                error_key=ErrorKey.INTERNAL_ERROR,
                status_code=503,
                error_detail="LOCAL_FINE_TUNE_JWT_SECRET not configured",
            )
        now = datetime.now(timezone.utc)
        payload: Dict[str, Any] = {
            "tenant_id": get_tenant_context(),
            "origin": settings.LOCAL_FINE_TUNING_CALL_ORIGIN,
            "iat": now,
            "exp": now + timedelta(seconds=self._TOKEN_TTL_SECONDS),
        }
        if context.exists():
            user_id = context.get("user_id")
            if user_id is not None:
                payload["user_id"] = str(user_id)
        return jwt.encode(
            payload, settings.LOCAL_FINE_TUNE_JWT_SECRET, algorithm=self._TOKEN_ALGORITHM
        )

    def _headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self._mint_token()}"}

    @staticmethod
    def _upstream_error_body(resp: httpx.Response) -> Any:
        """Return a body suitable for forwarding back to the caller.

        The local fine-tuning service uses the same AppException envelope as
        this backend: ``{error, error_code, error_key, error_detail}``. Pass it
        through unchanged. If the upstream returned a non-JSON body (e.g. a
        bare error string from an LB), wrap it in the same envelope so the
        frontend always has an ``error`` field to display.
        """
        try:
            body = resp.json()
        except ValueError:
            body = None
        if isinstance(body, (dict, list)):
            return body
        message = resp.text.strip() if resp.text else f"Upstream returned {resp.status_code}"
        return {
            "error": message,
            "error_code": resp.status_code,
            "error_key": "upstream_error",
        }

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: Optional[Any] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Any:
        url = f"{self._base_url()}/{path.lstrip('/')}"
        headers = self._headers()
        try:
            async with httpx.AsyncClient(timeout=settings.DEFAULT_TIMEOUT) as client:
                resp = await client.request(method, url, json=json, params=params, headers=headers)
        except httpx.RequestError as exc:
            logger.warning(f"Local fine-tune request error: {method} {url} → {exc}")
            raise AppException(
                error_key=ErrorKey.INTERNAL_ERROR,
                status_code=502,
                error_detail=f"Local fine-tune service unreachable: {exc}",
            ) from exc

        if resp.status_code >= 400:
            logger.warning(
                f"Local fine-tune upstream error: {method} {url} → {resp.status_code} {resp.text[:500]}"
            )
            raise UpstreamServiceError(
                status_code=resp.status_code,
                body=self._upstream_error_body(resp),
            )

        if resp.status_code == 204 or not resp.content:
            return None
        try:
            return resp.json()
        except ValueError as exc:
            raise AppException(
                error_key=ErrorKey.INTERNAL_ERROR,
                status_code=502,
                error_detail=f"Local fine-tune service returned non-JSON response: {exc}",
            ) from exc

    def _normalize_supported_models(self, raw: Any) -> List[LocalFineTuneSupportedModel]:
        items: List[Any] = []
        if isinstance(raw, list):
            items = raw
        elif isinstance(raw, dict):
            for key in ("items", "data", "results", "models", "rows"):
                value = raw.get(key)
                if isinstance(value, list):
                    items = value
                    break

        normalized: List[LocalFineTuneSupportedModel] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            model_id = item.get("id")
            if model_id is None or str(model_id) == "":
                continue
            name = (
                item.get("name")
                or item.get("display_name")
                or item.get("model_name")
                or item.get("model")
                or item.get("title")
                or model_id
            )
            normalized.append(LocalFineTuneSupportedModel(id=str(model_id), name=str(name)))
        return normalized

    async def list_supported_models(
        self, skip: int = 0, limit: int = 10
    ) -> List[LocalFineTuneSupportedModel]:
        raw = await self._request(
            "GET",
            "api/v1/supported-models",
            params={"skip": skip, "limit": limit},
        )
        return self._normalize_supported_models(raw)

    async def list_system_gpus(self) -> SystemGpusResponse:
        raw = await self._request("GET", "api/v1/system/gpus")
        return SystemGpusResponse.model_validate(raw)

    async def list_jobs(self) -> List[LocalFineTuneJob]:
        raw = await self._request(
            "GET",
            "api/v1/fine-tuning/jobs",
            params={"order_by": "created_at", "sort_direction": "desc"},
        )
        if not isinstance(raw, list):
            return []
        return [LocalFineTuneJob.model_validate(item) for item in raw]

    async def get_job(self, job_id: str) -> LocalFineTuneJob:
        raw = await self._request("GET", f"api/v1/fine-tuning/jobs/{job_id}")
        return LocalFineTuneJob.model_validate(raw)

    async def list_job_events(self, job_id: str) -> List[LocalFineTuneJobEvent]:
        raw = await self._request("GET", f"api/v1/fine-tuning/jobs/{job_id}/events")
        if not isinstance(raw, list):
            return []
        return [LocalFineTuneJobEvent.model_validate(item) for item in raw]

    async def create_job(self, payload: CreateLocalFineTuneJobRequest) -> LocalFineTuneJob:
        body = payload.model_dump(exclude_none=True)
        raw = await self._request("POST", "api/v1/fine-tuning/jobs", json=body)
        return LocalFineTuneJob.model_validate(raw)

    async def cancel_job(self, job_id: str) -> LocalFineTuneJob:
        raw = await self._request("POST", f"api/v1/fine-tuning/jobs/{job_id}/cancel")
        return LocalFineTuneJob.model_validate(raw)

    async def delete_job_files(
        self, job_id: str, params: DeleteJobFilesRequest
    ) -> DeleteJobFilesResponse:
        raw = await self._request(
            "DELETE",
            f"api/v1/fine-tuning/jobs/{job_id}/files",
            params={
                "delete_data_files": params.delete_data_files,
                "delete_checkpoints": params.delete_checkpoints,
                "delete_model": params.delete_model,
            },
        )
        return DeleteJobFilesResponse.model_validate(raw)

    async def list_deployments(self) -> List[LocalFineTuneDeployment]:
        raw = await self._request(
            "GET",
            "api/v1/deployments",
            params={"order_by": "created_at", "sort_direction": "desc"},
        )
        if not isinstance(raw, list):
            return []
        return [LocalFineTuneDeployment.model_validate(item) for item in raw]

    async def get_deployment(self, deployment_id: str) -> LocalFineTuneDeployment:
        raw = await self._request("GET", f"api/v1/deployments/{deployment_id}")
        return LocalFineTuneDeployment.model_validate(raw)

    async def create_deployment(
        self, payload: CreateDeploymentRequest
    ) -> LocalFineTuneDeployment:
        raw = await self._request(
            "POST",
            "api/v1/deployments",
            json=payload.model_dump(exclude_none=True),
        )
        return LocalFineTuneDeployment.model_validate(raw)

    async def stop_deployment(self, deployment_id: str) -> DeploymentStopResponse:
        raw = await self._request("DELETE", f"api/v1/deployments/{deployment_id}")
        return DeploymentStopResponse.model_validate(raw)

    async def deployment_health(self, deployment_id: str) -> LocalFineTuneDeploymentHealth:
        raw = await self._request("GET", f"api/v1/deployments/{deployment_id}/health")
        return LocalFineTuneDeploymentHealth.model_validate(raw)

    async def test_inference(
        self, deployment_id: str, message: str
    ) -> TestInferenceResponse:
        deployment = await self.get_deployment(deployment_id)

        server_host = urlparse(self._base_url()).hostname
        parsed_api = urlparse(deployment.api_url)
        rewritten_host = server_host or parsed_api.hostname or "localhost"
        if parsed_api.port:
            netloc = f"{rewritten_host}:{parsed_api.port}"
        else:
            netloc = rewritten_host
        rewritten = parsed_api._replace(netloc=netloc)
        chat_url = f"{rewritten.scheme}://{rewritten.netloc}/v1/chat/completions"

        body = {
            "model": deployment.model_path,
            "messages": [{"role": "user", "content": message}],
            "max_tokens": 512,
            "temperature": 0.7,
        }

        try:
            async with httpx.AsyncClient(timeout=settings.DEFAULT_TIMEOUT) as client:
                resp = await client.post(chat_url, json=body)
        except httpx.RequestError as exc:
            logger.warning(f"Local fine-tune deployment unreachable: POST {chat_url} → {exc}")
            raise AppException(
                error_key=ErrorKey.INTERNAL_ERROR,
                status_code=502,
                error_detail=f"Deployment unreachable: {exc}",
            ) from exc

        if resp.status_code >= 400:
            logger.warning(
                f"Local fine-tune deployment error: POST {chat_url} → {resp.status_code} {resp.text[:500]}"
            )
            raise UpstreamServiceError(
                status_code=resp.status_code,
                body=self._upstream_error_body(resp),
            )

        try:
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise AppException(
                error_key=ErrorKey.INTERNAL_ERROR,
                status_code=502,
                error_detail=f"Unexpected inference response shape: {exc}",
            ) from exc

        return TestInferenceResponse(content=content)
