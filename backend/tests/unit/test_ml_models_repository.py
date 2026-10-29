from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.repositories.ml_models import MLModelsRepository
from app.schemas.ml_model import MLModelCreate, MLModelRead, MLModelUpdate
from app.services import ml_models as ml_models_module
from app.services.ml_model_artifacts import ModelArtifactContract
from app.services.ml_models import (
    MLModelsService,
    merge_model_inference_params,
    stale_categorical_defaults,
)


def test_stale_default_check_distinguishes_boolean_from_integer_category():
    stale = stale_categorical_defaults(
        {"featureDefaults": {"kind": True}},
        {"kind": {"values": [1, 2], "normalize_keys": False}},
    )

    assert stale == ["kind"]


def test_merge_preserves_only_explicit_defaults_for_current_features():
    result = merge_model_inference_params(
        {"featureDefaults": {"hour": 12, "removed": 1}},
        ["hour", "is_weekend"],
        None,
    )

    assert result == {"featureDefaults": {"hour": 12}}


def test_merge_keeps_explicit_empty_defaults_empty():
    result = merge_model_inference_params(
        {"featureDefaults": {}},
        ["is_weekend"],
        None,
    )

    assert result is None


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


@pytest.mark.asyncio
async def test_service_rejects_create_when_artifact_contract_mismatches(monkeypatch):
    repository = MagicMock()
    repository.get_by_name = AsyncMock(return_value=None)
    repository.create = AsyncMock()
    validation_error = AppException(
        error_key=ErrorKey.ML_MODEL_ARTIFACT_INVALID,
        error_detail="Registry fields do not match the model file.",
    )
    validator = AsyncMock(side_effect=validation_error)
    monkeypatch.setattr(
        ml_models_module,
        "validate_model_artifact_registration",
        validator,
    )
    service = MLModelsService(repository)
    model = MLModelCreate(
        name="forecast",
        description="Forecast model",
        model_type="linear_regression",
        features=["hour"],
        target_variable="revenue",
        pkl_file="model.pkl",
    )

    with pytest.raises(AppException) as exc:
        await service.create(model)

    assert exc.value is validation_error
    validator.assert_awaited_once_with(
        "model.pkl",
        None,
        ["hour"],
        "revenue",
        artifact_contract=None,
    )
    repository.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_service_validates_effective_fields_when_features_change(monkeypatch):
    model_id = uuid4()
    existing = SimpleNamespace(
        features=["hour"],
        target_variable="revenue",
        pkl_file="model.pkl",
        pkl_file_id=None,
        inference_params=None,
    )
    repository = MagicMock()
    repository.get_by_id = AsyncMock(return_value=existing)
    repository.update = AsyncMock(return_value=existing)
    validator = AsyncMock()
    monkeypatch.setattr(
        ml_models_module,
        "validate_model_artifact_registration",
        validator,
    )
    service = MLModelsService(repository)

    await service.update(model_id, MLModelUpdate(features=["hour", "lag_24"]))

    validator.assert_awaited_once_with(
        "model.pkl",
        None,
        ["hour", "lag_24"],
        "revenue",
        artifact_contract=None,
    )
    repository.update.assert_awaited_once()


@pytest.mark.asyncio
async def test_service_does_not_revalidate_unchanged_legacy_contract_fields(
    monkeypatch,
):
    model_id = uuid4()
    existing = SimpleNamespace(
        features=["hour"],
        target_variable="revenue",
        pkl_file="legacy.pkl",
        pkl_file_id=None,
        inference_params=None,
    )
    repository = MagicMock()
    repository.get_by_id = AsyncMock(return_value=existing)
    repository.update = AsyncMock(return_value=existing)
    validator = AsyncMock()
    monkeypatch.setattr(
        ml_models_module,
        "validate_model_artifact_registration",
        validator,
    )
    service = MLModelsService(repository)

    await service.update(
        model_id,
        MLModelUpdate(
            description="Updated description",
            features=["hour"],
            target_variable="revenue",
            pkl_file="legacy.pkl",
            pkl_file_id=None,
        ),
    )

    validator.assert_not_awaited()
    repository.update.assert_awaited_once()


@pytest.mark.asyncio
async def test_service_passes_a_known_artifact_contract_to_validation(monkeypatch):
    repository = MagicMock()
    repository.get_by_name = AsyncMock(return_value=None)
    repository.create = AsyncMock()
    validator = AsyncMock()
    monkeypatch.setattr(ml_models_module, "validate_model_artifact_registration", validator)
    contract = ModelArtifactContract(features=("hour",), target_variable="revenue", feature_count=1)
    model = MLModelCreate(
        name="forecast",
        description="Forecast model",
        model_type="linear_regression",
        features=["hour"],
        target_variable="revenue",
        pkl_file_id=str(uuid4()),
    )

    await MLModelsService(repository).create(model, artifact_contract=contract)

    assert validator.await_args.kwargs["artifact_contract"] is contract
    repository.create.assert_awaited_once()


@pytest.mark.asyncio
async def test_recording_a_downloaded_copy_does_not_revalidate(monkeypatch):
    model_id = uuid4()
    repository = MagicMock()
    repository.update = AsyncMock()
    validator = AsyncMock()
    monkeypatch.setattr(ml_models_module, "validate_model_artifact_registration", validator)

    await MLModelsService(repository).record_local_pkl_file(model_id, "/data/ml_models/m.pkl")

    repository.update.assert_awaited_once_with(model_id, {"pkl_file": "/data/ml_models/m.pkl"})
    validator.assert_not_awaited()


@pytest.mark.asyncio
async def test_new_uploaded_file_ignores_caller_path_and_is_validated(monkeypatch):
    model_id = uuid4()
    old_file_id, new_file_id = uuid4(), uuid4()
    existing = SimpleNamespace(
        features=["hour"],
        target_variable="revenue",
        pkl_file="/data/ml_models/forecast_old.pkl",
        pkl_file_id=old_file_id,
        inference_params=None,
    )
    repository = MagicMock()
    repository.get_by_id = AsyncMock(return_value=existing)
    repository.update = AsyncMock(return_value=existing)
    validator = AsyncMock()
    monkeypatch.setattr(ml_models_module, "validate_model_artifact_registration", validator)

    await MLModelsService(repository).update(
        model_id,
        MLModelUpdate(
            pkl_file_id=str(new_file_id),
            pkl_file="/tmp/caller-controlled.pkl",
        ),
    )

    validator.assert_awaited_once_with(None, str(new_file_id), ["hour"], "revenue", artifact_contract=None)
    assert repository.update.await_args.args[1]["pkl_file"] is None


@pytest.mark.asyncio
async def test_same_file_id_as_uuid_or_str_is_not_a_change(monkeypatch):
    file_id = uuid4()
    existing = SimpleNamespace(
        features=["hour"],
        target_variable="revenue",
        pkl_file="/data/ml_models/forecast.pkl",
        pkl_file_id=file_id,
        inference_params=None,
    )
    repository = MagicMock()
    repository.get_by_id = AsyncMock(return_value=existing)
    repository.update = AsyncMock(return_value=existing)
    validator = AsyncMock()
    monkeypatch.setattr(ml_models_module, "validate_model_artifact_registration", validator)

    await MLModelsService(repository).update(uuid4(), MLModelUpdate(pkl_file_id=str(file_id)))

    validator.assert_not_awaited()
    assert "pkl_file" not in repository.update.await_args.args[1]


@pytest.mark.asyncio
async def test_taken_name_is_rejected_before_reading_the_artifact(monkeypatch):
    repository = MagicMock()
    repository.get_by_name = AsyncMock(return_value=SimpleNamespace(id=uuid4()))
    repository.get_by_id = AsyncMock()
    repository.update = AsyncMock()
    validator = AsyncMock()
    monkeypatch.setattr(ml_models_module, "validate_model_artifact_registration", validator)

    with pytest.raises(AppException) as exc:
        await MLModelsService(repository).update(uuid4(), MLModelUpdate(name="taken", features=["hour"]))

    assert exc.value.error_key is ErrorKey.ML_MODEL_NAME_EXISTS
    validator.assert_not_awaited()
    repository.update.assert_not_awaited()


@pytest.mark.asyncio
async def test_stale_pkl_file_from_the_edit_form_is_ignored(monkeypatch):
    file_id = uuid4()
    existing = SimpleNamespace(
        features=["hour"],
        target_variable="revenue",
        pkl_file="/data/ml_models/forecast_recorded.pkl",
        pkl_file_id=file_id,
        inference_params=None,
    )
    repository = MagicMock()
    repository.get_by_id = AsyncMock(return_value=existing)
    repository.update = AsyncMock(return_value=existing)
    validator = AsyncMock()
    monkeypatch.setattr(ml_models_module, "validate_model_artifact_registration", validator)

    await MLModelsService(repository).update(
        uuid4(),
        MLModelUpdate(description="new text", pkl_file=None, pkl_file_id=str(file_id), features=["hour"]),
    )

    validator.assert_not_awaited()
    assert "pkl_file" not in repository.update.await_args.args[1]


@pytest.mark.asyncio
async def test_feature_change_reads_the_recorded_copy_not_a_caller_path(monkeypatch):
    file_id = uuid4()
    existing = SimpleNamespace(
        features=["hour"],
        target_variable="revenue",
        pkl_file="/data/ml_models/forecast_recorded.pkl",
        pkl_file_id=file_id,
        inference_params=None,
    )
    repository = MagicMock()
    repository.get_by_id = AsyncMock(return_value=existing)
    repository.update = AsyncMock(return_value=existing)
    validator = AsyncMock()
    monkeypatch.setattr(ml_models_module, "validate_model_artifact_registration", validator)

    await MLModelsService(repository).update(
        uuid4(), MLModelUpdate(pkl_file="/etc/shadow", features=["hour", "lag_24"])
    )

    validator.assert_awaited_once_with(
        "/data/ml_models/forecast_recorded.pkl",
        str(file_id),
        ["hour", "lag_24"],
        "revenue",
        artifact_contract=None,
    )


@pytest.mark.asyncio
async def test_create_with_an_uploaded_file_ignores_the_caller_path(monkeypatch):
    repository = MagicMock()
    repository.get_by_name = AsyncMock(return_value=None)
    repository.create = AsyncMock()
    validator = AsyncMock()
    monkeypatch.setattr(ml_models_module, "validate_model_artifact_registration", validator)
    file_id = str(uuid4())

    await MLModelsService(repository).create(
        MLModelCreate(
            name="forecast",
            description="Forecast model",
            model_type="linear_regression",
            features=["hour"],
            target_variable="revenue",
            pkl_file="/nonexistent",
            pkl_file_id=file_id,
        )
    )

    validator.assert_awaited_once_with(None, file_id, ["hour"], "revenue", artifact_contract=None)
    created_model = repository.create.await_args.args[0]
    assert created_model.pkl_file is None
    assert str(created_model.pkl_file_id) == file_id
