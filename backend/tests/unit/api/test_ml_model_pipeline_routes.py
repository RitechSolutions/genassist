import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import Request

from app.api.v1.routes.ml_model_pipeline import promote_pipeline_run
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.core.exceptions.exception_handler import _app_exception_body
from app.schemas.ml_model_pipeline import MLModelPipelineRunPromote


def _request() -> Request:
    return Request({"type": "http", "headers": [], "query_string": b""})


@pytest.mark.asyncio
async def test_promote_pipeline_run_leaves_safe_error_for_global_handler(monkeypatch):
    monkeypatch.setenv("ENV", "prod")
    error_detail = (
        "This pipeline run cannot safely replace the model artifact. "
        "Run the pipeline again, then promote the new run."
    )
    error = AppException(
        error_key=ErrorKey.ML_PIPELINE_RUN_NOT_PROMOTABLE,
        error_detail=error_detail,
    )
    service = MagicMock()
    service.promote_run = AsyncMock(side_effect=error)

    with pytest.raises(AppException) as exc_info:
        await promote_pipeline_run(
            model_id=uuid.uuid4(),
            run_id=uuid.uuid4(),
            promote_data=MLModelPipelineRunPromote(),
            service=service,
        )

    assert exc_info.value is error
    body = _app_exception_body(_request(), exc_info.value)
    assert body["error_detail"] == error_detail
    assert body["error"] != ErrorKey.ML_PIPELINE_RUN_NOT_PROMOTABLE.value


@pytest.mark.asyncio
async def test_promote_pipeline_run_does_not_expose_or_restatus_internal_error(
    monkeypatch,
):
    monkeypatch.setenv("ENV", "prod")
    error = AppException(
        error_key=ErrorKey.INTERNAL_ERROR,
        status_code=503,
        error_detail="Storage failure for bucket secret-models at s3://internal/models",
    )
    service = MagicMock()
    service.promote_run = AsyncMock(side_effect=error)

    with pytest.raises(AppException) as exc_info:
        await promote_pipeline_run(
            model_id=uuid.uuid4(),
            run_id=uuid.uuid4(),
            promote_data=MLModelPipelineRunPromote(),
            service=service,
        )

    assert exc_info.value is error
    assert exc_info.value.status_code == 503
    body = _app_exception_body(_request(), exc_info.value)
    assert body["error_code"] == 503
    assert body["error"] == "An internal server error occurred. Please try again later."
    assert body["error_detail"] is None
    assert "secret-models" not in str(body)


@pytest.mark.asyncio
@pytest.mark.parametrize("error_key", [ErrorKey.NOT_FOUND, ErrorKey.ML_MODEL_NOT_FOUND])
async def test_promote_pipeline_run_returns_404_for_missing_resources(error_key):
    # Repositories raise "not found" with the default status 400.
    error = AppException(error_key=error_key)
    service = MagicMock()
    service.promote_run = AsyncMock(side_effect=error)

    with pytest.raises(AppException) as exc_info:
        await promote_pipeline_run(
            model_id=uuid.uuid4(),
            run_id=uuid.uuid4(),
            promote_data=MLModelPipelineRunPromote(),
            service=service,
        )

    assert exc_info.value is error
    assert exc_info.value.status_code == 404
    body = _app_exception_body(_request(), exc_info.value)
    assert body["error_code"] == 404
