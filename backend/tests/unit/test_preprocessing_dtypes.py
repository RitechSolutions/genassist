"""
DP-4: column types produced by preprocessing (e.g. a Change Column Data Type
step) must reach the next node, and Train Model must handle pandas' nullable
and extension dtypes without skipping columns or emitting warnings.
"""

import uuid
import warnings

import numpy as np
import pandas as pd
import pytest

from app.modules.workflow.engine.nodes.ml import ml_utils
from app.modules.workflow.engine.nodes.ml.train_model_node import TrainModelNode
from app.modules.workflow.engine.workflow_state import WorkflowState


def _typed_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "code": pd.Series(["001", "002", None], dtype=object),
            "count": pd.array([1, None, 3], dtype="Int64"),
            "flag": pd.array([True, None, False], dtype="boolean"),
            "when": pd.to_datetime(["2024-01-01", "2024-02-01", None]),
            "level": pd.Categorical(["low", "high", "low"]),
            "score": [1.5, 2.5, 3.5],
        }
    )


class TestColumnTypesSurviveTheCsvRoundTrip:
    @pytest.mark.asyncio
    async def test_saved_dtypes_are_restored_on_load(self, tmp_path, monkeypatch):
        monkeypatch.setattr(ml_utils, "DATA_VOLUME", tmp_path)
        df = _typed_frame()
        path = await ml_utils.save_data_to_csv(
            df.to_dict("records"),
            list(df.columns),
            "thread",
            suffix="_preprocess",
            dtypes={c: str(t) for c, t in df.dtypes.items()},
        )
        assert ml_utils.dtypes_sidecar_path(path).exists()

        _, loaded = ml_utils.load_csv_file(path)
        # Text stays text - a plain read_csv turned "001" into the number 1.
        assert loaded["code"].tolist()[:2] == ["001", "002"]
        assert str(loaded["count"].dtype) == "Int64"
        assert loaded["count"].isna().tolist() == [False, True, False]
        assert str(loaded["flag"].dtype) == "boolean"
        assert pd.api.types.is_datetime64_any_dtype(loaded["when"])
        assert isinstance(loaded["level"].dtype, pd.CategoricalDtype)
        assert str(loaded["score"].dtype) == "float64"

    def test_file_without_saved_dtypes_reads_exactly_as_before(self, tmp_path):
        path = tmp_path / "upload.csv"
        pd.DataFrame({"code": ["001"], "n": [1]}).to_csv(path, index=False)
        loaded = ml_utils.read_csv_with_dtypes(path)
        assert loaded["code"].tolist() == [1]  # pandas' own inference, unchanged
        assert str(loaded["n"].dtype) == "int64"

    def test_unusable_saved_dtypes_fall_back_to_a_plain_read(self, tmp_path):
        path = tmp_path / "edited.csv"
        pd.DataFrame({"n": ["not a number"]}).to_csv(path, index=False)
        ml_utils.dtypes_sidecar_path(path).write_text('{"n": "Int64"}')
        loaded = ml_utils.read_csv_with_dtypes(path)
        assert loaded["n"].tolist() == ["not a number"]

    def test_analysis_reports_the_preserved_types_and_categories(self, tmp_path):
        path = tmp_path / "typed.csv"
        df = _typed_frame()
        df.to_csv(path, index=False)
        ml_utils.write_dtypes_sidecar(path, df)
        analysis = ml_utils.analyze_csv_data(str(path))
        info = {c["name"]: c for c in analysis["columns_info"]}
        assert info["code"]["type"] == "categorical"
        assert info["code"]["categories"] == ["001", "002"]
        assert info["level"]["type"] == "categorical"
        assert info["level"]["categories"] == ["high", "low"]
        assert info["flag"]["type"] == "categorical"
        assert info["count"]["type"] == "numeric"


class TestNormalizeDtypesForTraining:
    def test_extension_dtypes_become_the_dtypes_train_model_selects_on(self):
        df = ml_utils.normalize_dtypes_for_training(
            pd.DataFrame(
                {
                    "int_na": pd.array([1, None], dtype="Int64"),
                    "int_full": pd.array([1, 2], dtype="Int64"),
                    "int32": np.array([1, 2], dtype="int32"),
                    "float32": np.array([1.5, 2.5], dtype="float32"),
                    "bool_na": pd.array([True, None], dtype="boolean"),
                    "bool_full": pd.array([True, False], dtype="boolean"),
                    "text": pd.array(["a", None], dtype="string"),
                    "cat": pd.Categorical(["x", "y"]),
                    "when": pd.to_datetime(["2024-01-01", None]),
                }
            )
        )
        assert str(df["int_na"].dtype) == "float64"
        assert str(df["int_full"].dtype) == "int64"
        assert str(df["int32"].dtype) == "int64"
        assert str(df["float32"].dtype) == "float64"
        assert str(df["bool_na"].dtype) == "float64"
        assert df["bool_full"].dtype == bool
        assert df["text"].dtype == object and df["text"].tolist()[0] == "a"
        assert pd.isna(df["text"].tolist()[1])
        assert df["cat"].dtype == object
        assert df["when"].dtype == object and pd.isna(df["when"].tolist()[1])

    def test_plain_dtypes_are_left_alone(self):
        original = pd.DataFrame({"i": [1, 2], "f": [1.0, np.nan], "s": ["a", "b"], "b": [True, False]})
        df = ml_utils.normalize_dtypes_for_training(original)
        assert df.dtypes.to_dict() == original.dtypes.to_dict()


class TestMissingValueFill:
    def test_constant_fill_on_object_column_emits_no_future_warning(self):
        series = pd.Series([1, None, 3], dtype=object)
        with warnings.catch_warnings():
            warnings.simplefilter("error", FutureWarning)
            filled = TrainModelNode._fill_missing(series, 0)
        assert filled.tolist() == [1, 0, 3]

    def test_text_number_fill_is_converted_for_a_numeric_column(self):
        assert TrainModelNode._coerce_fill_value(pd.Series([1.0, np.nan]), "2.5") == 2.5
        assert TrainModelNode._coerce_fill_value(pd.Series([1, 2]), " 0 ") == 0

    def test_non_numeric_fill_for_a_numeric_column_fails_clearly(self):
        from app.core.exceptions.exception_classes import AppException

        with pytest.raises(AppException) as exc_info:
            TrainModelNode._coerce_fill_value(pd.Series([1.0, np.nan], name="age"), "unknown")
        assert "age" in exc_info.value.error_detail
        assert "not a number" in exc_info.value.error_detail

    def test_text_fill_for_a_text_column_is_kept(self):
        assert TrainModelNode._coerce_fill_value(pd.Series(["a", None]), "missing") == "missing"


class TestPreprocessedTypesTrainEndToEnd:
    @pytest.mark.asyncio
    async def test_train_model_trains_on_preprocessed_nullable_columns(self, tmp_path):
        # A preprocessing output with nullable Int64/boolean and category
        # columns (as saved by the Data Preprocessing node) trains, with the
        # Int64 column scaled as numeric and the category one-hot encoded.
        rng = np.random.default_rng(1)
        n = 60
        df = pd.DataFrame(
            {
                "count": pd.array(rng.integers(0, 10, n), dtype="Int64"),
                "flag": pd.array(rng.choice([True, False], n), dtype="boolean"),
                "level": pd.Categorical(rng.choice(["a", "b", "c"], n)),
                "target": rng.normal(0, 1, n),
            }
        )
        path = tmp_path / "pre.csv"
        df.to_csv(path, index=False)
        ml_utils.write_dtypes_sidecar(path, df)

        node = TrainModelNode(node_id=str(uuid.uuid4()), node_config={}, state=WorkflowState(workflow={}))
        result = await node.process(
            {
                "name": f"dtypes-{uuid.uuid4().hex[:8]}",
                "modelType": "linear_regression",
                "fileUrl": str(path),
                "targetColumn": "target",
                "featureColumns": ["count", "flag", "level"],
                "validationSplit": 0.25,
                "scalingMethod": "standard",
                "outlierHandling": [{"columnName": "count", "strategy": "cap_outliers", "method": "iqr"}],
            }
        )
        assert result["success"] is True

        import pickle

        with open(result["model_file_path"], "rb") as f:
            metadata = pickle.load(f)["metadata"]
        assert "count" in metadata["scaled_columns"]
        assert "level" in metadata["categorical_columns"]
