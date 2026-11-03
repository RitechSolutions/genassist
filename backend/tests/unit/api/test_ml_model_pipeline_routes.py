import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.api.v1.routes.ml_model_pipeline import promote_pipeline_run
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.schemas.ml_model_pipeline import MLModelPipelineRunPromote


@pytest.mark.asyncio
async def test_promote_pipeline_run_returns_actionable_error_detail():
    error_detail = (
        "This pipeline run cannot safely replace the model artifact. "
        "Run the pipeline again, then promote the new run."
    )
    service = MagicMock()
    service.promote_run = AsyncMock(
        side_effect=AppException(
            error_key=ErrorKey.ML_PIPELINE_RUN_NOT_PROMOTABLE,
            error_detail=error_detail,
        )
    )

    with pytest.raises(HTTPException) as exc_info:
        await promote_pipeline_run(
            model_id=uuid.uuid4(),
            run_id=uuid.uuid4(),
            promote_data=MLModelPipelineRunPromote(),
            service=service,
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == error_detail
