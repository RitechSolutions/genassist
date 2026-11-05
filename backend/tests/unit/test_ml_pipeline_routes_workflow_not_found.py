"""The pipeline config routes report a missing or deleted workflow as 404."""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.v1.routes import ml_model_pipeline as routes
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException


def _service(method: str):
    service = MagicMock()
    setattr(
        service,
        method,
        AsyncMock(side_effect=AppException(status_code=404, error_key=ErrorKey.WORKFLOW_NOT_FOUND)),
    )
    return service


@pytest.mark.asyncio
async def test_create_returns_404_for_a_missing_workflow():
    with pytest.raises(HTTPException) as exc:
        await routes.create_pipeline_config(uuid4(), MagicMock(), service=_service("create"))
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_update_returns_404_for_a_missing_workflow():
    with pytest.raises(HTTPException) as exc:
        await routes.update_pipeline_config(uuid4(), uuid4(), MagicMock(), service=_service("update"))
    assert exc.value.status_code == 404
