from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.repositories.ml_models import MLModelsRepository
from app.schemas.ml_model import MLModelCreate, MLModelRead, MLModelUpdate
from app.services import ml_model_manager
from app.services import ml_models as ml_models_module
from app.services.ml_model_artifacts import ModelArtifactContract, RegistryContractCheck
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


@pytest.mark.asyncio
async def test_create_persists_training_metrics():
    db = MagicMock()
    transaction = MagicMock()
    transaction.__aenter__ = AsyncMock()
    transaction.__aexit__ = AsyncMock()
    db.begin_nested.return_value = transaction
    db.flush = AsyncMock()
    db.refresh = AsyncMock()

    repository = MLModelsRepository(db)
    metrics = {"mse": 0.25, "rmse": 0.5, "r2_score": 0.9}
    created = await repository.create(
        MLModelCreate(
            name="forecast",
            description="Forecast model",
            model_type="linear_regression",
            features=["hour"],
            target_variable="revenue",
        ),
        training_metrics=metrics,
    )

    assert created.training_metrics == metrics


@pytest.mark.parametrize(
    "inference_params",
    [
        {"featureDefaults": [0]},
        {"featureDefaults": {"hour": None}},
        {"featureDefaults": {"hour": {"value": 0}}},
        {"featureDefaults": {"hour": float("nan")}},
        {"ratioBaselineColumn": ""},
        {"useTrainingFills": "true"},
        {"useTrainingFills": 1},
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


@pytest.mark.parametrize("use_training_fills", [True, False])
def test_schema_accepts_training_fills_switch(use_training_fills):
    model = MLModelCreate(
        name="forecast",
        description="Forecast model",
        model_type="linear_regression",
        features=["hour"],
        target_variable="revenue",
        inference_params={"useTrainingFills": use_training_fills},
    )

    assert model.inference_params == {"useTrainingFills": use_training_fills}


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
async def test_create_saves_features_in_the_file_order_and_returns_the_notices(monkeypatch):
    repository = MagicMock()
    repository.get_by_name = AsyncMock(return_value=None)
    repository.create = AsyncMock(side_effect=lambda model, **_: SimpleNamespace(features=model.features))
    check = RegistryContractCheck(features=("hour", "lag_24"), notices=("Features were saved in order.",))
    monkeypatch.setattr(ml_models_module, "validate_model_artifact_registration", AsyncMock(return_value=check))
    model = MLModelCreate(
        name="forecast",
        description="Forecast model",
        model_type="linear_regression",
        features=["lag_24", "hour"],
        target_variable="revenue",
        pkl_file_id=str(uuid4()),
    )

    notices = []
    created = await MLModelsService(repository).create(model, notices=notices)

    assert repository.create.await_args.args[0].features == ["hour", "lag_24"]
    assert repository.create.await_args.args[0].pkl_file is None
    assert notices == ["Features were saved in order."]
    assert not hasattr(created, "registration_notices")


@pytest.mark.asyncio
async def test_update_saves_features_in_the_file_order_and_returns_the_notices(monkeypatch):
    model_id = uuid4()
    existing = SimpleNamespace(
        id=model_id,
        features=["hour", "lag_24"],
        target_variable="revenue",
        pkl_file=None,
        pkl_file_id=uuid4(),
        inference_params=None,
    )
    repository = MagicMock()
    repository.get_by_id = AsyncMock(return_value=existing)
    repository.update = AsyncMock(return_value=SimpleNamespace())
    check = RegistryContractCheck(features=("hour", "lag_24"), notices=("Target not checked.",))
    monkeypatch.setattr(ml_models_module, "validate_model_artifact_registration", AsyncMock(return_value=check))

    notices = []
    updated = await MLModelsService(repository).update(
        model_id, MLModelUpdate(features=["lag_24", "hour"]), notices=notices
    )

    assert repository.update.await_args.args[1]["features"] == ["hour", "lag_24"]
    assert notices == ["Target not checked."]
    assert not hasattr(updated, "registration_notices")


def test_read_schema_has_no_notices_for_a_stored_model():
    now = datetime.now(timezone.utc)
    stored = SimpleNamespace(
        id=uuid4(),
        name="forecast",
        description="Forecast model",
        model_type="linear_regression",
        features=["hour"],
        target_variable="revenue",
        inference_params=None,
        pkl_file=None,
        pkl_file_id=None,
        training_metrics=None,
        created_at=now,
        updated_at=now,
    )

    assert MLModelRead.model_validate(stored).registration_notices == []


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


@pytest.mark.parametrize(
    "recorded_name,reads_recorded_copy",
    [("{model_id}_current.pkl", True), ("{model_id}_earlier.pkl", False), ("forecast.pkl", True)],
)
def test_artifact_source_skips_a_copy_of_an_earlier_upload(monkeypatch, recorded_name, reads_recorded_copy):
    model_id, file_id = uuid4(), str(uuid4())
    monkeypatch.setattr(
        ml_model_manager,
        "_downloaded_model_path",
        lambda _model_id, _file_id: f"/data/ml_models/{model_id}_current.pkl",
    )
    recorded = f"/data/ml_models/{recorded_name.format(model_id=model_id)}"
    existing = SimpleNamespace(id=model_id, pkl_file=recorded)

    source = MLModelsService._artifact_source(existing, {}, file_id, file_id_changed=False)

    assert source == ((recorded if reads_recorded_copy else None), file_id)


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


def _upload_record(**overrides):
    record = {
        "id": uuid4(),
        "path": "ml_models/5f0c.pkl",
        "file_extension": "pkl",
        "created_by": "user-a",
        "created_at": datetime.now(timezone.utc),
        "storage_provider": "local",
        "storage_path": "/data",
    }
    record.update(overrides)
    return SimpleNamespace(**record)


def _discard_setup(monkeypatch, record, referenced=False, user="user-a"):
    repository = MagicMock()
    repository.is_file_referenced = AsyncMock(return_value=referenced)
    file_manager = MagicMock()
    file_manager.get_file_by_id = AsyncMock(return_value=record)
    file_manager.delete_file = AsyncMock()
    file_manager.storage_provider = SimpleNamespace(name="local", get_base_path=lambda: "/data")
    monkeypatch.setattr(ml_models_module, "get_current_user_id", lambda: user)
    return MLModelsService(repository), file_manager


@pytest.mark.asyncio
async def test_discard_removes_the_callers_unused_recent_upload(monkeypatch, tmp_path):
    record = _upload_record()
    monkeypatch.setattr(ml_models_module, "ML_MODELS_UPLOAD_DIR", str(tmp_path))
    copy = tmp_path / f"{record.id}.pkl"
    copy.write_bytes(b"copy")
    service, file_manager = _discard_setup(monkeypatch, record)

    await service.discard_unused_upload(record.id, file_manager)

    file_manager.delete_file.assert_awaited_once_with(record.id)
    assert not copy.exists()


@pytest.mark.asyncio
async def test_discard_accepts_a_tenant_scoped_s3_upload(monkeypatch):
    from app.core.tenant_scope import clear_tenant_context, set_tenant_context

    record = _upload_record(path="tenants/tenant-a/ml_models/5f0c.pkl", storage_provider="s3", storage_path="bucket")
    service, file_manager = _discard_setup(monkeypatch, record)
    file_manager.storage_provider = SimpleNamespace(name="s3", get_base_path=lambda: "bucket")

    set_tenant_context("tenant-a")
    try:
        await service.discard_unused_upload(record.id, file_manager)
    finally:
        clear_tenant_context()

    file_manager.delete_file.assert_awaited_once_with(record.id)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "overrides,referenced,user",
    [
        ({}, False, "user-b"),  # someone else's upload
        ({}, True, "user-a"),  # a model uses it
        ({"path": "uploads/5f0c.csv", "file_extension": "csv"}, False, "user-a"),  # not an ML model upload
        ({"file_extension": "csv"}, False, "user-a"),
        ({"created_by": None}, False, None),  # no recorded uploader
        ({"created_at": datetime(2020, 1, 1, tzinfo=timezone.utc)}, False, "user-a"),  # old upload
        ({"storage_path": "/old-folder"}, False, "user-a"),  # saved under other File Manager settings
        ({"storage_provider": "s3"}, False, "user-a"),
    ],
)
async def test_discard_refuses_any_other_file_with_not_found(monkeypatch, overrides, referenced, user):
    record = _upload_record(**overrides)
    service, file_manager = _discard_setup(monkeypatch, record, referenced=referenced, user=user)

    with pytest.raises(AppException) as exc:
        await service.discard_unused_upload(record.id, file_manager)

    assert exc.value.error_key is ErrorKey.FILE_NOT_FOUND
    assert exc.value.status_code == 404
    file_manager.delete_file.assert_not_awaited()


@pytest.mark.asyncio
async def test_discard_of_a_missing_file_is_not_found(monkeypatch):
    service, file_manager = _discard_setup(monkeypatch, _upload_record())
    file_manager.get_file_by_id = AsyncMock(side_effect=AppException(error_key=ErrorKey.DATASOURCE_NOT_FOUND))

    with pytest.raises(AppException) as exc:
        await service.discard_unused_upload(uuid4(), file_manager)

    assert exc.value.status_code == 404
    file_manager.delete_file.assert_not_awaited()


@pytest.mark.asyncio
async def test_discard_counts_a_model_that_points_at_the_upload_path(monkeypatch, tmp_path):
    record = _upload_record()
    monkeypatch.setattr(ml_models_module, "ML_MODELS_UPLOAD_DIR", str(tmp_path))
    service, file_manager = _discard_setup(monkeypatch, record, referenced=True)

    with pytest.raises(AppException):
        await service.discard_unused_upload(record.id, file_manager)

    checked_id, checked_paths = service.repository.is_file_referenced.await_args.args
    assert checked_id == record.id
    assert "/data/ml_models/5f0c.pkl" in checked_paths
    assert str(tmp_path / f"{record.id}.pkl") in checked_paths
    file_manager.delete_file.assert_not_awaited()


@pytest.mark.asyncio
async def test_is_file_referenced_matches_any_spelling_of_the_id_and_the_path():
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

    file_id = uuid4()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        # Only the columns the query reads; the real table uses Postgres-only types.
        await conn.execute(text(
            "CREATE TABLE ml_models (id CHAR(32) PRIMARY KEY, pkl_file TEXT, pkl_file_id TEXT, is_deleted INTEGER)"
        ))
    async with AsyncSession(engine) as db:
        repository = MLModelsRepository(db)

        async def stored(pkl_file_id=None, pkl_file=None, is_deleted=0):
            await db.execute(text("DELETE FROM ml_models"))
            await db.execute(
                text("INSERT INTO ml_models VALUES (:id, :pkl_file, :pkl_file_id, :is_deleted)"),
                {"id": uuid4().hex, "pkl_file": pkl_file, "pkl_file_id": pkl_file_id, "is_deleted": is_deleted},
            )

        for spelling in (str(file_id), str(file_id).upper(), f"{{{file_id}}}", file_id.hex, f"urn:uuid:{file_id}",
                         f"uuid:{file_id}", f"urn:{file_id}"):
            await stored(pkl_file_id=spelling)
            assert await repository.is_file_referenced(file_id), spelling

        await stored(pkl_file="/data/ml_models/x.pkl")
        assert await repository.is_file_referenced(file_id, ["/data/ml_models/x.pkl"])
        assert not await repository.is_file_referenced(file_id, ["/data/ml_models/other.pkl"])

        await stored(pkl_file_id=str(file_id), is_deleted=1)
        assert not await repository.is_file_referenced(file_id)

        await stored(pkl_file_id=str(uuid4()))
        assert not await repository.is_file_referenced(file_id)
    await engine.dispose()


def test_client_schemas_do_not_accept_training_metrics():
    update = MLModelUpdate(training_metrics={"accuracy": 1.0})
    assert "training_metrics" not in update.model_dump(exclude_unset=True)


def test_normalize_training_metrics_keeps_finite_numbers_only():
    import numpy as np

    from app.services.ml_models import normalize_training_metrics

    assert normalize_training_metrics(None) is None
    assert normalize_training_metrics("bad") == {}
    assert normalize_training_metrics(
        {
            "r2_score": np.float64(0.8),
            "mse": 1,
            "rmse": float("nan"),
            "flag": True,
            "confusion_matrix": [[1, 0], [0, 1]],
            "note": "0.5",
        }
    ) == {"r2_score": 0.8, "mse": 1.0}


def _existing_model(file_id):
    return SimpleNamespace(
        features=["hour"],
        target_variable="revenue",
        pkl_file="/data/ml_models/forecast_old.pkl",
        pkl_file_id=file_id,
        inference_params=None,
        training_metrics={"r2_score": 0.9},
    )


@pytest.mark.asyncio
async def test_replacing_the_file_without_metrics_clears_stored_metrics(monkeypatch):
    existing = _existing_model(uuid4())
    repository = MagicMock()
    repository.get_by_id = AsyncMock(return_value=existing)
    repository.update = AsyncMock(return_value=existing)
    monkeypatch.setattr(ml_models_module, "validate_model_artifact_registration", AsyncMock())

    await MLModelsService(repository).update(uuid4(), MLModelUpdate(pkl_file_id=str(uuid4())))

    assert repository.update.await_args.args[1]["training_metrics"] == {}


@pytest.mark.asyncio
async def test_replacing_the_file_with_metrics_stores_them(monkeypatch):
    existing = _existing_model(uuid4())
    repository = MagicMock()
    repository.get_by_id = AsyncMock(return_value=existing)
    repository.update = AsyncMock(return_value=existing)
    monkeypatch.setattr(ml_models_module, "validate_model_artifact_registration", AsyncMock())

    await MLModelsService(repository).update(
        uuid4(), MLModelUpdate(pkl_file_id=str(uuid4())), training_metrics={"r2_score": 0.7}
    )

    assert repository.update.await_args.args[1]["training_metrics"] == {"r2_score": 0.7}


@pytest.mark.asyncio
async def test_edits_that_keep_the_file_keep_stored_metrics(monkeypatch):
    file_id = uuid4()
    existing = _existing_model(file_id)
    repository = MagicMock()
    repository.get_by_id = AsyncMock(return_value=existing)
    repository.update = AsyncMock(return_value=existing)
    monkeypatch.setattr(ml_models_module, "validate_model_artifact_registration", AsyncMock())

    await MLModelsService(repository).update(
        uuid4(), MLModelUpdate(pkl_file_id=str(file_id), description="new text")
    )

    assert "training_metrics" not in repository.update.await_args.args[1]


def test_service_is_built_by_the_injector():
    # Train Model registration gets MLModelsService from the injector.
    from injector import get_bindings

    assert "repository" in get_bindings(MLModelsService.__init__)


# ---- Train Data Source uploads (TDS-22) ----


def _training_upload(**overrides):
    return _upload_record(**{
        "path": "uploads/5f0c.csv",
        "file_extension": "csv",
        "file_metadata": {"upload_purpose": "training_data"},
        **overrides,
    })


def _training_discard_setup(monkeypatch, record, referenced=False, user="user-a"):
    service, file_manager = _discard_setup(monkeypatch, record, user=user)
    service.repository.is_training_file_referenced = AsyncMock(return_value=referenced)
    return service, file_manager


@pytest.mark.asyncio
@pytest.mark.parametrize("extension", ["csv", "parquet", "xlsx", "xlsm", "json", "jsonl", "ndjson", "CSV"])
async def test_training_discard_removes_the_callers_unused_upload(monkeypatch, extension):
    record = _training_upload(path=f"uploads/5f0c.{extension}", file_extension=extension)
    service, file_manager = _training_discard_setup(monkeypatch, record)

    await service.discard_unused_training_upload(record.id, file_manager)

    file_manager.delete_file.assert_awaited_once_with(record.id)


@pytest.mark.asyncio
async def test_training_discard_accepts_an_upload_a_day_old():
    """The dialog may stay open for hours between picking a file and closing it."""
    from datetime import timedelta

    record = _training_upload(created_at=datetime.now(timezone.utc) - timedelta(hours=23))
    monkeypatch = pytest.MonkeyPatch()
    try:
        service, file_manager = _training_discard_setup(monkeypatch, record)
        await service.discard_unused_training_upload(record.id, file_manager)
    finally:
        monkeypatch.undo()

    file_manager.delete_file.assert_awaited_once_with(record.id)


@pytest.mark.asyncio
async def test_training_discard_accepts_a_tenant_scoped_s3_upload(monkeypatch):
    from app.core.tenant_scope import clear_tenant_context, set_tenant_context

    record = _training_upload(path="tenants/tenant-a/uploads/5f0c.csv", storage_provider="s3", storage_path="bucket")
    service, file_manager = _training_discard_setup(monkeypatch, record)
    file_manager.storage_provider = SimpleNamespace(name="s3", get_base_path=lambda: "bucket")

    set_tenant_context("tenant-a")
    try:
        await service.discard_unused_training_upload(record.id, file_manager)
    finally:
        clear_tenant_context()

    file_manager.delete_file.assert_awaited_once_with(record.id)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "overrides,referenced,user",
    [
        ({}, True, "user-a"),  # a workflow version or ML model still points at it
        ({"file_metadata": {}}, False, "user-a"),  # a knowledge base file in the same folder
        ({"file_metadata": None}, False, "user-a"),
        ({"file_metadata": {"upload_purpose": "other"}}, False, "user-a"),
        ({}, False, "user-b"),  # someone else's upload
        ({"path": "ml_models/5f0c.pkl", "file_extension": "pkl"}, False, "user-a"),  # an ML model file
        ({"path": "uploads/5f0c.pdf", "file_extension": "pdf"}, False, "user-a"),  # not a training file
        ({"path": "kb/5f0c.csv"}, False, "user-a"),  # another feature's folder
        ({"created_by": None}, False, None),  # no recorded uploader
        ({"created_at": datetime(2020, 1, 1, tzinfo=timezone.utc)}, False, "user-a"),  # old upload
        ({"created_at": None}, False, "user-a"),
        ({"storage_path": "/old-folder"}, False, "user-a"),  # saved under other File Manager settings
        ({"storage_provider": "s3"}, False, "user-a"),
    ],
)
async def test_training_discard_refuses_any_other_file_with_not_found(monkeypatch, overrides, referenced, user):
    record = _training_upload(**overrides)
    service, file_manager = _training_discard_setup(monkeypatch, record, referenced=referenced, user=user)

    with pytest.raises(AppException) as exc:
        await service.discard_unused_training_upload(record.id, file_manager)

    assert exc.value.error_key is ErrorKey.FILE_NOT_FOUND
    assert exc.value.status_code == 404
    file_manager.delete_file.assert_not_awaited()


@pytest.mark.asyncio
async def test_training_discard_of_a_missing_file_is_not_found(monkeypatch):
    service, file_manager = _training_discard_setup(monkeypatch, _training_upload())
    file_manager.get_file_by_id = AsyncMock(side_effect=AppException(error_key=ErrorKey.FILE_NOT_FOUND))

    with pytest.raises(AppException) as exc:
        await service.discard_unused_training_upload(uuid4(), file_manager)

    assert exc.value.status_code == 404
    file_manager.delete_file.assert_not_awaited()


@pytest.mark.asyncio
async def test_training_discard_checks_the_local_path_a_node_may_keep(monkeypatch):
    record = _training_upload()
    service, file_manager = _training_discard_setup(monkeypatch, record, referenced=True)

    with pytest.raises(AppException):
        await service.discard_unused_training_upload(record.id, file_manager)

    checked_id, checked_paths = service.repository.is_training_file_referenced.await_args.args
    assert checked_id == record.id
    assert "/data/uploads/5f0c.csv" in checked_paths
    file_manager.delete_file.assert_not_awaited()


@pytest.mark.asyncio
async def test_is_training_file_referenced_by_a_workflow_version_or_a_model():
    import json
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

    file_id = uuid4()
    path = "/data/uploads/5f0c_100%.csv"
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        # Only the columns the queries read; the real tables use Postgres-only types.
        await conn.execute(text(
            "CREATE TABLE ml_models (id CHAR(32) PRIMARY KEY, pkl_file TEXT, pkl_file_id TEXT, is_deleted INTEGER)"
        ))
        await conn.execute(text("CREATE TABLE workflows (id CHAR(32) PRIMARY KEY, nodes TEXT, is_deleted INTEGER)"))
    async with AsyncSession(engine) as db:
        repository = MLModelsRepository(db)

        async def workflow(data, is_deleted=0):
            await db.execute(text("DELETE FROM workflows"))
            await db.execute(text("DELETE FROM ml_models"))
            nodes = [{"id": "n1", "type": "trainDataSourceNode", "data": data}]
            await db.execute(
                text("INSERT INTO workflows VALUES (:id, :nodes, :is_deleted)"),
                {"id": uuid4().hex, "nodes": json.dumps(nodes, ensure_ascii=False), "is_deleted": is_deleted},
            )

        # Any live version that names the file by id (any case) or by local path keeps it.
        for data in ({"csvFileId": str(file_id)}, {"csvFileId": str(file_id).upper()}, {"csvFilePath": path}):
            await workflow(data)
            assert await repository.is_training_file_referenced(file_id, [path]), data

        # A path with a backslash or quote is stored escaped in the nodes JSON.
        for odd_path in ('C:\\data\\uploads\\a"b.csv', 'C:\\Données\\uploads\\é.csv'):
            await workflow({"csvFilePath": odd_path})
            assert await repository.is_training_file_referenced(file_id, [odd_path]), odd_path

        # A deleted version, another file, or a path that only matches as a LIKE pattern do not.
        await workflow({"csvFileId": str(file_id)}, is_deleted=1)
        assert not await repository.is_training_file_referenced(file_id, [path])
        await workflow({"csvFileId": str(uuid4())})
        assert not await repository.is_training_file_referenced(file_id, [path])
        await workflow({"csvFilePath": "/data/uploads/5f0c_100X.csv"})
        assert not await repository.is_training_file_referenced(file_id, [path])

        # An ML model pointing at the file keeps it too.
        await workflow({})
        await db.execute(
            text("INSERT INTO ml_models VALUES (:id, NULL, :pkl_file_id, 0)"),
            {"id": uuid4().hex, "pkl_file_id": str(file_id)},
        )
        assert await repository.is_training_file_referenced(file_id)
    await engine.dispose()
