import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import Request

from app.api.v1.routes.ml_model_pipeline import promote_pipeline_run
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.core.exceptions.exception_handler import _app_exception_body
from app.db.models.ml_model_pipeline import PipelineRunStatus
from app.schemas.ml_model_pipeline import MLModelPipelineRunPromote, MLModelPipelineRunRead


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


def _stored_run(execution_output):
    """A run row as the pipeline-runs routes read it from the database."""
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        id=uuid.uuid4(),
        model_id=uuid.uuid4(),
        pipeline_config_id=uuid.uuid4(),
        workflow_id=uuid.uuid4(),
        status=PipelineRunStatus.COMPLETED,
        started_at=now,
        completed_at=now,
        error_message=None,
        execution_output=execution_output,
        execution_id=None,
        workflow=None,
        created_at=now,
        updated_at=now,
    )


@pytest.mark.parametrize(
    "stored, expected",
    [
        ("plain text", {"output": "plain text"}),
        (["a"], {"output": ["a"]}),
        (3, {"output": 3}),
        (None, None),
        ({"output": "chat reply"}, {"output": "chat reply"}),
        ({"output": {"pkl_file_id": "f"}}, {"output": {"pkl_file_id": "f"}}),
    ],
)
def test_run_read_keeps_any_stored_execution_output_as_an_object(stored, expected):
    # The run list and run detail routes serialize every row through this schema;
    # a non-object execution_output used to fail validation and return a 500.
    run = MLModelPipelineRunRead.model_validate(_stored_run(stored))

    assert run.execution_output == expected
