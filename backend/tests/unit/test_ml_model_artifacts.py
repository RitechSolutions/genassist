import pickle
import threading
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import numpy as np
import pandas as pd
import pytest
from sklearn.linear_model import LinearRegression

from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.services import ml_model_artifacts
from app.services.ml_model_artifacts import (
    _UNREADABLE_DETAIL,
    ModelArtifactContract,
    extract_model_artifact_contract,
    load_model_artifact_contract,
    validate_model_artifact_registration,
    validate_registry_contract,
)
from app.services.ml_model_manager import get_ml_model_manager

_X = np.arange(12, dtype=float).reshape(6, 2)
_Y = np.arange(6, dtype=float)


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


def _contract(features=("hour", "lag_24"), target="revenue"):
    return ModelArtifactContract(features=features, target_variable=target, feature_count=len(features))


def _named_raw_model():
    return LinearRegression().fit(pd.DataFrame(_X, columns=["hour", "lag_24"]), _Y)


def _unnamed_raw_model():
    return LinearRegression().fit(_X, _Y)


class TestExtractContract:
    def test_extracts_ordered_v2_contract(self):
        assert extract_model_artifact_contract(_artifact()) == _contract()

    @pytest.mark.parametrize(
        "artifact,error_fragment",
        [
            ({"model": object()}, "safe, unambiguous feature-name order"),
            (_artifact(schema_version=True), "invalid metadata schema version"),
            (_artifact(schema_version=3), "supports up to v2"),
            (_artifact(features=[]), "invalid feature_columns metadata"),
            (_artifact(features=["hour", "hour"]), "invalid feature_columns metadata"),
            (_artifact(target=""), "invalid target_column metadata"),
        ],
    )
    def test_rejects_invalid_or_incomplete_v2_contracts(self, artifact, error_fragment):
        with pytest.raises(AppException) as exc:
            extract_model_artifact_contract(artifact)

        assert exc.value.error_key is ErrorKey.ML_MODEL_ARTIFACT_INVALID
        assert error_fragment in exc.value.error_detail

    def test_metadata_without_schema_version_is_rejected_like_inference(self):
        artifact = {"model": object(), "metadata": {"feature_columns": ["hour", "lag_24"]}, "version": "v2.0"}

        with pytest.raises(AppException) as exc:
            extract_model_artifact_contract(artifact)

        assert exc.value.error_key is ErrorKey.ML_MODEL_ARTIFACT_INVALID
        assert "does not declare a metadata schema version" in exc.value.error_detail

    def test_dict_without_metadata_is_read_as_a_raw_model_like_inference(self):
        artifact = {"model": _named_raw_model(), "version": "v2.0"}

        contract = extract_model_artifact_contract(artifact)

        assert contract.features == ("hour", "lag_24")

    def test_numpy_integer_feature_count_without_names_is_rejected(self):
        model = SimpleNamespace(n_features_in_=np.int64(3))

        with pytest.raises(AppException) as exc:
            extract_model_artifact_contract(model)

        assert "safe, unambiguous feature-name order" in exc.value.error_detail

    def test_raw_model_uses_recorded_feature_names(self):
        contract = extract_model_artifact_contract(_named_raw_model())

        assert contract.features == ("hour", "lag_24")
        assert contract.target_variable is None
        assert contract.feature_count == 2
        assert contract.module_root == "sklearn"
        assert contract.feature_order_source == "estimator"

    def test_raw_model_without_names_is_rejected_like_inference(self):
        with pytest.raises(AppException) as exc:
            extract_model_artifact_contract(_unnamed_raw_model())

        assert "safe, unambiguous feature-name order" in exc.value.error_detail

    def test_raw_model_with_duplicate_recorded_names_is_rejected(self):
        model = SimpleNamespace(feature_names_in_=np.array(["a", "b", "a"]))

        with pytest.raises(AppException) as exc:
            extract_model_artifact_contract(model)

        assert "safe, unambiguous feature-name order" in exc.value.error_detail

    def test_raw_model_without_names_or_count_is_rejected(self):
        with pytest.raises(AppException) as exc:
            extract_model_artifact_contract(object())

        assert exc.value.error_key is ErrorKey.ML_MODEL_ARTIFACT_INVALID
        assert "safe, unambiguous feature-name order" in exc.value.error_detail

    def test_lightgbm_feature_names_use_inference_normalization(self):
        class LightGBMModel:
            n_features_in_ = 1
            feature_name_ = ["monthly_charges"]

        LightGBMModel.__module__ = "lightgbm.sklearn"
        contract = extract_model_artifact_contract(LightGBMModel())

        validate_registry_contract(contract, ["monthly charges"], "revenue")


class TestValidateRegistryContract:
    def test_accepts_exact_match(self):
        validate_registry_contract(_contract(), ["hour", "lag_24"], "revenue")

    @pytest.mark.parametrize(
        "registered,fragment",
        [
            (["hour"], "Missing features: 'lag_24'."),
            (["hour", "lag_24", "is_weekend"], "Features not in the model: 'is_weekend'."),
            (["hour", "lag24"], "Missing features: 'lag_24'. Features not in the model: 'lag24'."),
            (["hour", "lag_24", "lag_24"], "Duplicate features: 'lag_24'."),
        ],
    )
    def test_reports_the_specific_feature_problem(self, registered, fragment):
        with pytest.raises(AppException) as exc:
            validate_registry_contract(_contract(), registered, "revenue")

        assert exc.value.error_key is ErrorKey.ML_MODEL_ARTIFACT_INVALID
        assert fragment.lower() in exc.value.error_detail.lower()

    def test_accepts_the_same_unique_features_in_a_different_order(self):
        validate_registry_contract(_contract(), ["lag_24", "hour"], "revenue")

    def test_accepts_reordered_sklearn_estimator_features(self):
        contract = extract_model_artifact_contract(_named_raw_model())

        validate_registry_contract(contract, ["lag_24", "hour"], "anything")

    def test_target_mismatch_is_reported_first(self):
        with pytest.raises(AppException) as exc:
            validate_registry_contract(_contract(), ["lag_24", "hour"], "sessions")

        detail = exc.value.error_detail
        assert "Target must be 'revenue', not 'sessions'" in detail
        assert "Feature order" not in detail

    def test_large_mismatch_stays_short_and_keeps_the_target(self):
        features = tuple(f"feature_with_a_long_descriptive_name_{index:02d}" for index in range(30))
        registered = [name.replace("_12", "_x12") for name in features]

        with pytest.raises(AppException) as exc:
            validate_registry_contract(_contract(features), registered[:-5], "sessions")

        detail = exc.value.error_detail
        assert len(detail) < 450
        assert "Target must be 'revenue'" in detail
        assert "(+3 more)" in detail

    def test_worst_case_detail_is_capped(self):
        expected = tuple(f"expected_feature_name_that_is_long_{index}" for index in range(6))
        registered = [f"\x00\x01\x02 registered_wrong_name_{index % 4}" * 2 for index in range(8)]

        with pytest.raises(AppException) as exc:
            validate_registry_contract(_contract(expected), registered, "x" * 60)

        assert len(exc.value.error_detail) <= 440
        assert exc.value.error_detail.startswith("Registry fields do not match the model file. Target must be")

    def test_raw_model_contract_skips_the_target_check(self):
        contract = ModelArtifactContract(features=("hour", "lag_24"), target_variable=None, feature_count=2)

        validate_registry_contract(contract, ["hour", "lag_24"], "anything")

    def test_count_only_contract_is_rejected_even_when_the_count_matches(self):
        contract = ModelArtifactContract(features=None, target_variable=None, feature_count=2)

        with pytest.raises(AppException) as exc:
            validate_registry_contract(contract, ["a", "b"], "revenue")

        assert "does not record a safe feature-name order" in exc.value.error_detail

    def test_count_only_contract_rejects_duplicate_registry_features(self):
        contract = ModelArtifactContract(features=None, target_variable=None, feature_count=2)

        with pytest.raises(AppException) as exc:
            validate_registry_contract(contract, ["age", "age"], "revenue")

        assert "Duplicate features: 'age'." in exc.value.error_detail


class TestLoadContract:
    @pytest.mark.asyncio
    async def test_reads_local_artifact_without_touching_the_model_cache(self, tmp_path):
        artifact_path = tmp_path / "model.pkl"
        artifact_path.write_bytes(pickle.dumps(_named_raw_model()))
        manager = get_ml_model_manager()
        validated_before = set(manager._validated_files)

        contract = await load_model_artifact_contract(str(artifact_path), None)

        assert contract.features == ("hour", "lag_24")
        assert set(manager._validated_files) == validated_before

    @pytest.mark.asyncio
    async def test_reads_off_the_event_loop(self, monkeypatch, tmp_path):
        artifact_path = tmp_path / "model.pkl"
        artifact_path.write_bytes(b"unused")
        loop_thread = threading.get_ident()
        read_threads = []

        def fake_read(_path):
            read_threads.append(threading.get_ident())
            return _artifact()

        monkeypatch.setattr(ml_model_artifacts, "_read_artifact_sync", fake_read)

        await load_model_artifact_contract(str(artifact_path), None)

        assert read_threads and read_threads[0] != loop_thread

    @pytest.mark.asyncio
    @pytest.mark.parametrize("kind", ["missing", "device", "directory", "not_a_pickle", "too_large"])
    async def test_every_local_read_failure_returns_the_same_message(self, monkeypatch, tmp_path, kind):
        # Distinct messages would let a caller probe the server filesystem through pkl_file.
        paths = {"missing": str(tmp_path / "gone.pkl"), "device": "/dev/null", "directory": str(tmp_path)}
        if kind == "not_a_pickle":
            (tmp_path / "passwd").write_text("root:x:0:0:root:/root:/bin/bash\n")
            paths[kind] = str(tmp_path / "passwd")
        if kind == "too_large":
            (tmp_path / "model.pkl").write_bytes(pickle.dumps(_artifact()))
            paths[kind] = str(tmp_path / "model.pkl")
            monkeypatch.setattr(ml_model_artifacts, "MAX_ARTIFACT_BYTES", 8)

        with pytest.raises(AppException) as exc:
            await load_model_artifact_contract(paths[kind], None)

        assert exc.value.error_key is ErrorKey.ML_MODEL_ARTIFACT_INVALID
        assert exc.value.error_detail == _UNREADABLE_DETAIL

    @pytest.mark.asyncio
    async def test_missing_local_copy_falls_back_to_the_uploaded_file(self, monkeypatch, tmp_path):
        downloaded_paths = []

        async def fake_download(_file_id, destination_path):
            downloaded_paths.append(destination_path)
            Path(destination_path).write_bytes(pickle.dumps(_named_raw_model()))

        monkeypatch.setattr(ml_model_artifacts, "_download_artifact", fake_download)

        contract = await load_model_artifact_contract(str(tmp_path / "gone.pkl"), "artifact-id")

        assert contract.features == ("hour", "lag_24")
        assert len(downloaded_paths) == 1
        assert not Path(downloaded_paths[0]).exists()


class TestDownloadArtifact:
    @pytest.mark.asyncio
    async def test_oversized_record_is_rejected_before_download(self, monkeypatch, tmp_path):
        file_manager = MagicMock(
            get_file_by_id=AsyncMock(return_value=SimpleNamespace(id=uuid4(), size=600 * 1024 * 1024)),
            download_file_to_path=AsyncMock(),
        )
        monkeypatch.setattr(ml_model_artifacts, "_file_manager", lambda: file_manager)

        with pytest.raises(AppException) as exc:
            await ml_model_artifacts._download_artifact(str(uuid4()), str(tmp_path / "model.pkl"))

        assert exc.value.error_detail == _UNREADABLE_DETAIL
        file_manager.download_file_to_path.assert_not_awaited()

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "lookup",
        [
            AsyncMock(return_value=None),
            AsyncMock(side_effect=AppException(error_key=ErrorKey.DATASOURCE_NOT_FOUND)),
        ],
    )
    async def test_missing_record_returns_the_fixed_message(self, monkeypatch, tmp_path, lookup):
        file_manager = MagicMock(get_file_by_id=lookup, download_file_to_path=AsyncMock())
        monkeypatch.setattr(ml_model_artifacts, "_file_manager", lambda: file_manager)

        with pytest.raises(AppException) as exc:
            await ml_model_artifacts._download_artifact(str(uuid4()), str(tmp_path / "model.pkl"))

        assert exc.value.error_key is ErrorKey.ML_MODEL_ARTIFACT_INVALID
        assert exc.value.error_detail == _UNREADABLE_DETAIL

    @pytest.mark.asyncio
    async def test_non_uuid_id_returns_the_fixed_message(self, tmp_path):
        with pytest.raises(AppException) as exc:
            await ml_model_artifacts._download_artifact("not-a-uuid", str(tmp_path / "model.pkl"))

        assert exc.value.status_code == 400
        assert exc.value.error_detail == _UNREADABLE_DETAIL

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "lookup,download",
        [
            (AsyncMock(side_effect=RuntimeError("db down")), AsyncMock()),
            (
                AsyncMock(return_value=SimpleNamespace(id=uuid4(), size=10)),
                AsyncMock(side_effect=AppException(error_key=ErrorKey.INTERNAL_ERROR)),
            ),
        ],
    )
    async def test_storage_or_database_failure_is_a_retryable_server_error(
        self, monkeypatch, tmp_path, lookup, download
    ):
        file_manager = MagicMock(get_file_by_id=lookup, download_file_to_path=download)
        monkeypatch.setattr(ml_model_artifacts, "_file_manager", lambda: file_manager)

        with pytest.raises(AppException) as exc:
            await ml_model_artifacts._download_artifact(str(uuid4()), str(tmp_path / "model.pkl"))

        assert exc.value.error_key is ErrorKey.INTERNAL_ERROR
        assert exc.value.status_code == 503

    @pytest.mark.asyncio
    async def test_slow_download_times_out_as_a_server_error(self, monkeypatch, tmp_path):
        import asyncio

        async def slow_download(_file_id, _path):
            await asyncio.sleep(5)

        file_manager = MagicMock(
            get_file_by_id=AsyncMock(return_value=SimpleNamespace(id=uuid4(), size=10)),
            download_file_to_path=slow_download,
        )
        monkeypatch.setattr(ml_model_artifacts, "_file_manager", lambda: file_manager)
        monkeypatch.setattr(ml_model_artifacts, "ARTIFACT_DOWNLOAD_TIMEOUT_SECONDS", 0.05)

        with pytest.raises(AppException) as exc:
            await ml_model_artifacts._download_artifact(str(uuid4()), str(tmp_path / "model.pkl"))

        assert exc.value.status_code == 503


class TestLoadContractEdgeCases:
    @pytest.mark.asyncio
    async def test_no_artifact_means_no_contract(self):
        assert await load_model_artifact_contract(None, None) is None

    @pytest.mark.asyncio
    async def test_known_contract_skips_reading_the_artifact(self, monkeypatch):
        def fail_read(_path):
            raise AssertionError("artifact should not be read")

        monkeypatch.setattr(ml_model_artifacts, "_read_artifact_sync", fail_read)

        await validate_model_artifact_registration(
            None, "artifact-id", ["hour", "lag_24"], "revenue", artifact_contract=_contract()
        )
