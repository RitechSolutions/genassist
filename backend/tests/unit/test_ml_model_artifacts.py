from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.services import ml_model_artifacts
from app.services.ml_model_artifacts import (
    ModelArtifactContract,
    extract_model_artifact_contract,
    load_model_artifact_contract,
    validate_registry_contract,
)


def _artifact(
    features=None,
    target="revenue",
    schema_version=2,
):
    return {
        "model": object(),
        "metadata": {
            "metadata_schema_version": schema_version,
            "feature_columns": ["hour", "lag_24"] if features is None else features,
            "target_column": target,
        },
        "version": "v2.0",
    }


def test_extracts_ordered_artifact_contract():
    contract = extract_model_artifact_contract(_artifact())

    assert contract == ModelArtifactContract(
        features=("hour", "lag_24"),
        target_variable="revenue",
    )


@pytest.mark.parametrize(
    "artifact,error_fragment",
    [
        ({"model": object()}, "does not contain self-described feature metadata"),
        (_artifact(schema_version=True), "invalid metadata schema version"),
        (_artifact(schema_version=3), "supports up to v2"),
        (_artifact(features=[]), "invalid feature_columns metadata"),
        (_artifact(features=["hour", "hour"]), "invalid feature_columns metadata"),
        (_artifact(target=""), "invalid target_column metadata"),
    ],
)
def test_rejects_invalid_or_incomplete_artifact_contracts(artifact, error_fragment):
    with pytest.raises(AppException) as exc:
        extract_model_artifact_contract(artifact)

    assert exc.value.error_key is ErrorKey.ML_INFERENCE_INPUT_INVALID
    assert error_fragment in exc.value.error_detail


def test_rejects_feature_order_and_target_mismatches_together():
    contract = ModelArtifactContract(
        features=("hour", "lag_24"),
        target_variable="revenue",
    )

    with pytest.raises(AppException) as exc:
        validate_registry_contract(contract, ["lag_24", "hour"], "sessions")

    assert exc.value.error_key is ErrorKey.ML_INFERENCE_INPUT_INVALID
    assert "including order" in exc.value.error_detail
    assert "'sessions'" in exc.value.error_detail
    assert "'revenue'" in exc.value.error_detail


@pytest.mark.parametrize(
    "registered_features",
    [
        ["hour"],
        ["hour", "lag_24", "is_weekend"],
        ["lag_24", "hour"],
    ],
)
def test_rejects_missing_extra_or_reordered_registry_features(registered_features):
    contract = ModelArtifactContract(
        features=("hour", "lag_24"),
        target_variable="revenue",
    )

    with pytest.raises(AppException) as exc:
        validate_registry_contract(contract, registered_features, "revenue")

    assert "Features must match exactly, including order" in exc.value.error_detail


def test_accepts_exact_registry_contract_match():
    validate_registry_contract(
        ModelArtifactContract(
            features=("hour", "lag_24"),
            target_variable="revenue",
        ),
        ["hour", "lag_24"],
        "revenue",
    )


@pytest.mark.asyncio
async def test_loads_local_artifact_through_model_manager(monkeypatch, tmp_path):
    artifact_path = tmp_path / "model.pkl"
    manager = MagicMock(load_artifact=AsyncMock(return_value=_artifact()))
    monkeypatch.setattr(ml_model_artifacts, "get_ml_model_manager", lambda: manager)

    contract = await load_model_artifact_contract(str(artifact_path), None)

    assert contract.features == ("hour", "lag_24")
    manager.load_artifact.assert_awaited_once_with(str(artifact_path))


@pytest.mark.asyncio
async def test_remote_artifact_uses_an_isolated_temporary_path(monkeypatch):
    downloaded_paths = []

    async def fake_download(_file_id, destination_path):
        downloaded_paths.append(destination_path)
        Path(destination_path).write_bytes(b"artifact")
        return destination_path

    manager = MagicMock(load_artifact=AsyncMock(return_value=_artifact()))
    monkeypatch.setattr(ml_model_artifacts, "get_ml_model_manager", lambda: manager)
    monkeypatch.setattr(ml_model_artifacts, "download_pkl_file", fake_download)

    contract = await load_model_artifact_contract(None, "artifact-id")

    assert contract.target_variable == "revenue"
    assert len(downloaded_paths) == 1
    assert not Path(downloaded_paths[0]).exists()
    manager.load_artifact.assert_awaited_once_with(downloaded_paths[0])
