from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.repositories.ml_models import MLModelsRepository
from app.schemas.ml_model import MLModelCreate, MLModelRead, MLModelUpdate
from app.services.ml_models import MLModelsService, stale_categorical_defaults


def test_stale_default_check_distinguishes_boolean_from_integer_category():
    stale = stale_categorical_defaults(
        {"featureDefaults": {"kind": True}},
        {"kind": {"values": [1, 2], "normalize_keys": False}},
    )

    assert stale == ["kind"]


@pytest.mark.asyncio
async def test_create_persists_inference_params():
    db = MagicMock()
    transaction = MagicMock()
    transaction.__aenter__ = AsyncMock()
    transaction.__aexit__ = AsyncMock()
    db.begin_nested.return_value = transaction
    db.flush = AsyncMock()
    db.refresh = AsyncMock()

    repository = MLModelsRepository(db)
    created = await repository.create(
        MLModelCreate(
            name="forecast",
            description="Forecast model",
            model_type="linear_regression",
            features=["hour"],
            target_variable="revenue",
            inference_params={"featureDefaults": {"hour": 0}},
        )
    )

    assert created.inference_params == {"featureDefaults": {"hour": 0}}


@pytest.mark.parametrize(
    "inference_params",
    [
        {"featureDefaults": [0]},
        {"featureDefaults": {"hour": None}},
        {"featureDefaults": {"hour": {"value": 0}}},
        {"featureDefaults": {"hour": float("nan")}},
        {"ratioBaselineColumn": ""},
    ],
)
def test_schema_rejects_invalid_inference_params(inference_params):
    with pytest.raises(ValidationError):
        MLModelCreate(
            name="forecast",
            description="Forecast model",
            model_type="linear_regression",
            features=["hour"],
            target_variable="revenue",
            inference_params=inference_params,
        )


def test_update_schema_rejects_invalid_inference_params():
    with pytest.raises(ValidationError):
        MLModelUpdate(inference_params={"featureDefaults": [0]})


@pytest.mark.parametrize("value", ["null", "NaN", "None"])
def test_schema_allows_missing_sentinel_as_a_potential_category(value):
    model = MLModelUpdate(inference_params={"featureDefaults": {"kind": value}})

    assert model.inference_params == {"featureDefaults": {"kind": value}}


def test_read_schema_allows_legacy_inference_params():
    model = MLModelRead(
        id=uuid4(),
        name="legacy",
        description="Legacy model",
        model_type="linear_regression",
        features=["hour"],
        target_variable="revenue",
        inference_params={"ratioBaselineColumn": ""},
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )

    assert model.inference_params == {"ratioBaselineColumn": ""}


@pytest.mark.asyncio
async def test_service_rejects_create_defaults_for_unknown_features():
    repository = MagicMock()
    repository.get_by_name = AsyncMock(return_value=None)
    repository.create = AsyncMock()
    service = MLModelsService(repository)

    with pytest.raises(AppException) as exc:
        await service.create(
            MLModelCreate(
                name="forecast",
                description="Forecast model",
                model_type="linear_regression",
                features=["hour"],
                target_variable="revenue",
                inference_params={"featureDefaults": {"unknown": 0}},
            )
        )

    assert exc.value.error_key is ErrorKey.ML_INFERENCE_INPUT_INVALID
    assert "unknown" in exc.value.error_detail
    repository.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_service_rejects_feature_update_that_orphans_a_default():
    model_id = uuid4()
    existing = MagicMock(
        features=["hour", "lag_24"],
        inference_params={"featureDefaults": {"lag_24": 0}},
    )
    repository = MagicMock()
    repository.get_by_id = AsyncMock(return_value=existing)
    repository.update = AsyncMock()
    service = MLModelsService(repository)

    with pytest.raises(AppException) as exc:
        await service.update(model_id, MLModelUpdate(features=["hour"]))

    assert exc.value.error_key is ErrorKey.ML_INFERENCE_INPUT_INVALID
    assert "lag_24" in exc.value.error_detail
    repository.update.assert_not_awaited()
