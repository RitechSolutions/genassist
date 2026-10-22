"""Compatibility tests for supported ML model pickle artifacts.

The allowlist shared by the static validator and the restricted loader must
keep accepting the artifacts the product actually serves: fitted scikit-learn
and XGBoost models, saved either as the Train Model payload
(``{"model", "metadata", "version"}``) or as a raw model pickled directly,
which is the legacy format of the local PBP fixtures.
"""

import itertools
import pickle
import threading
from collections import defaultdict
from datetime import datetime

import numpy as np
import pandas as pd
import pytest
from sklearn.cluster import KMeans
from sklearn.compose import ColumnTransformer, TransformedTargetRegressor
from sklearn.decomposition import PCA
from sklearn.ensemble import (
    ExtraTreesClassifier,
    ExtraTreesRegressor,
    GradientBoostingClassifier,
    GradientBoostingRegressor,
    HistGradientBoostingClassifier,
    HistGradientBoostingRegressor,
    IsolationForest,
    RandomForestClassifier,
    RandomForestRegressor,
)
from sklearn.impute import SimpleImputer
from sklearn.linear_model import (
    ElasticNet,
    Lasso,
    LinearRegression,
    LogisticRegression,
    Ridge,
    SGDClassifier,
    SGDRegressor,
)
from sklearn.model_selection import (
    GridSearchCV,
    GroupKFold,
    KFold,
    RepeatedKFold,
    RepeatedStratifiedKFold,
    ShuffleSplit,
    StratifiedKFold,
    StratifiedShuffleSplit,
    TimeSeriesSplit,
)
from sklearn.neighbors import KNeighborsClassifier, KNeighborsRegressor
from sklearn.neural_network import MLPClassifier, MLPRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import (
    FunctionTransformer,
    MaxAbsScaler,
    MinMaxScaler,
    OneHotEncoder,
    OrdinalEncoder,
    PolynomialFeatures,
    PowerTransformer,
    QuantileTransformer,
    RobustScaler,
    StandardScaler,
)
from sklearn.svm import SVC, SVR
from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor

from app.core.utils.model_validator import validate_pickle_file_safe
from app.core.utils.safe_pickle import safe_pickle_load
from app.modules.workflow.engine.nodes.ml import model_registry
from app.modules.workflow.engine.nodes.ml.hyperparameter_spaces import HYPERPARAMETER_SPACES
from app.services.ml_model_manager import MLModelManager, _load_pickle_sync

try:
    import xgboost as xgb
except ImportError:
    xgb = None

_RNG = np.random.default_rng(66748)
_X = _RNG.normal(size=(80, 4))
_Y_REGRESSION = _X @ np.array([1.5, -2.0, 0.5, 3.0]) + _RNG.normal(scale=0.1, size=80)
_Y_CLASSIFICATION = (_Y_REGRESSION > np.median(_Y_REGRESSION)).astype(int)
_Y_MULTICLASS = np.digitize(_Y_REGRESSION, np.quantile(_Y_REGRESSION, [0.25, 0.5, 0.75]))
_Y_STRING_CLASSIFICATION = np.array(["low", "medium", "high", "top"])[_Y_MULTICLASS]
_X_FRAME = pd.DataFrame(_X, columns=list("abcd"))

_REGRESSORS = {
    "extra_trees": lambda: ExtraTreesRegressor(n_estimators=5, random_state=0),
    "random_forest": lambda: RandomForestRegressor(n_estimators=5, random_state=0),
    "gradient_boosting": lambda: GradientBoostingRegressor(n_estimators=5, random_state=0),
    "decision_tree": lambda: DecisionTreeRegressor(max_depth=3, random_state=0),
    "linear_regression": LinearRegression,
    "ridge": Ridge,
    "lasso": lambda: Lasso(alpha=0.01),
    "elastic_net": lambda: ElasticNet(alpha=0.01),
    "svm": SVR,
    "knn": lambda: KNeighborsRegressor(n_neighbors=3),
    "neural_network": lambda: MLPRegressor(hidden_layer_sizes=(4,), max_iter=50, random_state=0),
}

_CLASSIFIERS = {
    "extra_trees": lambda: ExtraTreesClassifier(n_estimators=5, random_state=0),
    "random_forest": lambda: RandomForestClassifier(n_estimators=5, random_state=0),
    "gradient_boosting": lambda: GradientBoostingClassifier(n_estimators=5, random_state=0),
    "decision_tree": lambda: DecisionTreeClassifier(max_depth=3, random_state=0),
    "logistic_regression": LogisticRegression,
    "svm": SVC,
    "knn": lambda: KNeighborsClassifier(n_neighbors=3),
    "neural_network": lambda: MLPClassifier(hidden_layer_sizes=(4,), max_iter=50, random_state=0),
}

if xgb is not None:
    _REGRESSORS["xgboost"] = lambda: xgb.XGBRegressor(n_estimators=8, max_depth=3, random_state=0)
    _CLASSIFIERS["xgboost"] = lambda: xgb.XGBClassifier(n_estimators=8, max_depth=3, random_state=0)

# Preprocessing steps found in pipelines saved by the Train Model node.
_PIPELINE_STEPS = {
    "max_abs_scaler": MaxAbsScaler,
    "min_max_scaler": MinMaxScaler,
    "standard_scaler": StandardScaler,
    "robust_scaler": RobustScaler,
    "power_transformer": PowerTransformer,
    "quantile_transformer": lambda: QuantileTransformer(n_quantiles=20, random_state=0),
    "polynomial_features": lambda: PolynomialFeatures(degree=2),
    "pca": lambda: PCA(n_components=2, random_state=0),
}

_PARAMETER_VARIANTS = {
    "gradient_boosting_classifier_multiclass": (
        lambda: GradientBoostingClassifier(n_estimators=5, random_state=0),
        _Y_MULTICLASS,
    ),
    "gradient_boosting_classifier_string_labels": (
        lambda: GradientBoostingClassifier(n_estimators=5, random_state=0),
        _Y_STRING_CLASSIFICATION,
    ),
    "gradient_boosting_regressor_absolute_error": (
        lambda: GradientBoostingRegressor(n_estimators=5, loss="absolute_error", random_state=0),
        _Y_REGRESSION,
    ),
    "gradient_boosting_regressor_huber": (
        lambda: GradientBoostingRegressor(n_estimators=5, loss="huber", random_state=0),
        _Y_REGRESSION,
    ),
    "gradient_boosting_regressor_quantile": (
        lambda: GradientBoostingRegressor(n_estimators=5, loss="quantile", random_state=0),
        _Y_REGRESSION,
    ),
    "gradient_boosting_classifier_exponential": (
        lambda: GradientBoostingClassifier(n_estimators=5, loss="exponential", random_state=0),
        _Y_CLASSIFICATION,
    ),
    "mlp_regressor_sgd": (
        lambda: MLPRegressor(hidden_layer_sizes=(4,), max_iter=50, random_state=0, solver="sgd"),
        _Y_REGRESSION,
    ),
    "mlp_classifier_sgd": (
        lambda: MLPClassifier(hidden_layer_sizes=(4,), max_iter=50, random_state=0, solver="sgd"),
        _Y_CLASSIFICATION,
    ),
    "knn_regressor_ball_tree": (
        lambda: KNeighborsRegressor(algorithm="ball_tree", n_neighbors=3),
        _Y_REGRESSION,
    ),
    "knn_regressor_manhattan": (
        lambda: KNeighborsRegressor(algorithm="kd_tree", metric="manhattan", n_neighbors=3),
        _Y_REGRESSION,
    ),
    "knn_regressor_chebyshev": (
        lambda: KNeighborsRegressor(algorithm="kd_tree", metric="chebyshev", n_neighbors=3),
        _Y_REGRESSION,
    ),
}

_REGRESSION_ONLY_MODELS = frozenset({"elastic_net", "lasso_regression", "linear_regression", "ridge_regression"})
_CLASSIFICATION_ONLY_MODELS = frozenset({"logistic_regression"})
_SEARCH_TARGETS = {
    "regression": _Y_REGRESSION,
    "binary": _Y_CLASSIFICATION,
    "multiclass": _Y_MULTICLASS,
}


def _search_space_cases():
    cases = []
    for model_type in model_registry.VALID_MODEL_TYPES:
        dependency = model_registry.OPTIONAL_MODEL_DEPENDENCIES.get(model_type)
        dependency_available = dependency is None or dependency[1]()

        if model_type in _REGRESSION_ONLY_MODELS:
            tasks = ("regression",)
        elif model_type in _CLASSIFICATION_ONLY_MODELS:
            tasks = ("binary", "multiclass")
        else:
            tasks = tuple(_SEARCH_TARGETS)

        categorical_space = {
            name: specification["choices"]
            for name, specification in HYPERPARAMETER_SPACES.get(model_type, {}).items()
            if specification["type"] == "categorical"
        }
        for values in itertools.product(*categorical_space.values()):
            overrides = dict(zip(categorical_space, values))
            params = {**model_registry.MODEL_DEFAULT_PARAMS[model_type], **overrides}
            combination = ",".join(f"{name}={value!r}" for name, value in overrides.items()) or "defaults"
            for task in tasks:
                label = f"{model_type}-{task}-{combination}"
                case = (label, model_type, task, params)
                if dependency_available:
                    cases.append(pytest.param(case, id=label))
                else:
                    cases.append(
                        pytest.param(
                            case,
                            id=label,
                            marks=pytest.mark.skip(reason=f"{dependency[0]} is not installed"),
                        )
                    )
    return cases


_SEARCH_SPACE_CASES = _search_space_cases()


@pytest.fixture(scope="module", params=_SEARCH_SPACE_CASES)
def search_space_model(request):
    _label, model_type, task, params = request.param
    model = model_registry.build_estimator(model_type, task != "regression", params)
    model.fit(_X_FRAME, _SEARCH_TARGETS[task])
    return model


@pytest.fixture(scope="module", autouse=True)
def _isolate_working_directory(tmp_path_factory):
    # CatBoost writes catboost_info/ into the working directory while fitting,
    # including in the module-scoped search_space_model fixture.
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.chdir(tmp_path_factory.mktemp("fit-cwd"))
        yield


def _fit(factory, y):
    model = factory()
    model.fit(_X, y)
    return model


def _validate_and_load(tmp_path, artifact, protocol=pickle.HIGHEST_PROTOCOL):
    return _validate_and_load_bytes(tmp_path, pickle.dumps(artifact, protocol=protocol))


def _validate_and_load_bytes(tmp_path, data, *, encoding="ASCII"):
    pickle_file = tmp_path / "model.pkl"
    pickle_file.write_bytes(data)

    is_valid, error = validate_pickle_file_safe(str(pickle_file))
    assert is_valid is True, error
    assert error is None

    with open(pickle_file, "rb") as f:
        return safe_pickle_load(f, encoding=encoding)


def _numpy_1_protocol_5_pickle(value):
    from numpy._core import numeric

    frombuffer = numeric._frombuffer
    original_module = frombuffer.__module__
    try:
        frombuffer.__module__ = "numpy.core.numeric"
        return pickle.dumps(value, protocol=5)
    finally:
        frombuffer.__module__ = original_module


def _numpy_1_masked_array_pickle(value):
    masked_array = np.ma.MaskedArray
    original_module = masked_array.__module__
    try:
        masked_array.__module__ = "numpy.ma.core"
        return pickle.dumps(value)
    finally:
        masked_array.__module__ = original_module


class TestNumPyCompatibility:
    @pytest.mark.parametrize("protocol", [0, 1, 2])
    def test_legacy_protocol_array_roundtrips(self, tmp_path, protocol):
        array = np.arange(6, dtype=np.int64)

        loaded = _validate_and_load(tmp_path, array, protocol=protocol)

        np.testing.assert_array_equal(loaded, array)

    def test_numpy_1_protocol_5_array_roundtrips(self, tmp_path):
        array = np.arange(6, dtype=np.int64)

        loaded = _validate_and_load_bytes(tmp_path, _numpy_1_protocol_5_pickle(array))

        np.testing.assert_array_equal(loaded, array)

    def test_numpy_1_masked_array_roundtrips(self, tmp_path):
        masked = np.ma.array([1.0, 2.0, 3.0], mask=[False, True, False])

        loaded = _validate_and_load_bytes(tmp_path, _numpy_1_masked_array_pickle(masked))

        np.testing.assert_array_equal(loaded.mask, masked.mask)
        np.testing.assert_array_equal(loaded.filled(0), masked.filled(0))

    def test_numpy_1_grid_search_cv_results_roundtrip(self, tmp_path):
        model = GridSearchCV(Ridge(), {"alpha": [0.1, 1.0]}, cv=2).fit(_X, _Y_REGRESSION)

        loaded = _validate_and_load_bytes(tmp_path, _numpy_1_masked_array_pickle(model))

        np.testing.assert_array_equal(loaded.predict(_X), model.predict(_X))


class TestLegacyPickleCompatibility:
    @pytest.mark.parametrize(
        ("value", "protocol"),
        [
            ({1, 2}, 2),
            ({1, 2}, 3),
            (frozenset({1, 2}), 2),
            (b"", 0),
            (b"", 2),
            (defaultdict(list, {"a": [1]}), 2),
        ],
    )
    def test_legacy_builtin_roundtrips(self, tmp_path, value, protocol):
        loaded = _validate_and_load(tmp_path, value, protocol=protocol)

        assert loaded == value
        assert type(loaded) is type(value)

    def test_python2_protocol_zero_string_uses_latin1(self, tmp_path):
        loaded = _validate_and_load_bytes(tmp_path, b"S'\\xf8'\n.", encoding="latin1")

        assert loaded == "ø"

    def test_reused_memo_slot_matches_cpython(self, tmp_path):
        loaded = _validate_and_load_bytes(tmp_path, b"(I1\np0\nI2\np0\nt.")

        assert loaded == (1, 2)


class TestReviewedArtifactCompatibility:
    @pytest.mark.parametrize(
        ("factory", "target"),
        [
            (lambda: HistGradientBoostingClassifier(max_iter=5, random_state=0), _Y_CLASSIFICATION),
            (lambda: HistGradientBoostingRegressor(max_iter=5, random_state=0), _Y_REGRESSION),
            (lambda: SGDClassifier(max_iter=20, random_state=0), _Y_CLASSIFICATION),
            (lambda: SGDRegressor(max_iter=20, random_state=0), _Y_REGRESSION),
        ],
    )
    def test_reviewed_estimator_preserves_predictions(self, tmp_path, factory, target):
        model = _fit(factory, target)

        loaded = _validate_and_load(tmp_path, model)

        assert type(loaded) is type(model)
        np.testing.assert_array_equal(loaded.predict(_X), model.predict(_X))

    @pytest.mark.parametrize(
        "factory",
        [
            lambda: KMeans(n_clusters=3, n_init=2, random_state=0),
            lambda: IsolationForest(n_estimators=5, random_state=0),
        ],
    )
    def test_reviewed_unsupervised_estimator_preserves_predictions(self, tmp_path, factory):
        model = factory().fit(_X)

        loaded = _validate_and_load(tmp_path, model)

        assert type(loaded) is type(model)
        np.testing.assert_array_equal(loaded.predict(_X), model.predict(_X))

    def test_imputer_column_transformer_pipeline_preserves_predictions(self, tmp_path):
        input_data = _X.copy()
        input_data[0, 0] = np.nan
        model = Pipeline(
            [
                ("features", ColumnTransformer([("numbers", SimpleImputer(strategy="median"), [0, 1, 2, 3])])),
                ("model", RandomForestRegressor(n_estimators=5, random_state=0)),
            ]
        ).fit(input_data, _Y_REGRESSION)

        loaded = _validate_and_load(tmp_path, model)

        np.testing.assert_array_equal(loaded.predict(input_data), model.predict(input_data))

    def test_grid_search_preserves_predictions(self, tmp_path):
        model = GridSearchCV(Ridge(), {"alpha": [0.1, 1.0]}, cv=2).fit(_X, _Y_REGRESSION)

        loaded = _validate_and_load(tmp_path, model)

        np.testing.assert_array_equal(loaded.predict(_X), model.predict(_X))

    @pytest.mark.parametrize(
        "cv",
        [
            lambda: KFold(n_splits=3, shuffle=True, random_state=0),
            lambda: RepeatedKFold(n_splits=2, n_repeats=2, random_state=0),
            lambda: ShuffleSplit(n_splits=2, random_state=0),
            lambda: TimeSeriesSplit(n_splits=3),
        ],
    )
    def test_grid_search_with_cv_splitter_preserves_predictions(self, tmp_path, cv):
        model = GridSearchCV(Ridge(), {"alpha": [0.1, 1.0]}, cv=cv()).fit(_X, _Y_REGRESSION)

        loaded = _validate_and_load(tmp_path, model)

        np.testing.assert_array_equal(loaded.predict(_X), model.predict(_X))

    @pytest.mark.parametrize(
        "cv",
        [
            lambda: StratifiedKFold(n_splits=3, shuffle=True, random_state=0),
            lambda: RepeatedStratifiedKFold(n_splits=2, n_repeats=2, random_state=0),
            lambda: StratifiedShuffleSplit(n_splits=2, random_state=0),
        ],
    )
    def test_grid_search_with_stratified_cv_splitter_preserves_predictions(self, tmp_path, cv):
        model = GridSearchCV(LogisticRegression(max_iter=200), {"C": [0.1, 1.0]}, cv=cv()).fit(_X, _Y_CLASSIFICATION)

        loaded = _validate_and_load(tmp_path, model)

        np.testing.assert_array_equal(loaded.predict(_X), model.predict(_X))

    def test_grid_search_with_group_k_fold_preserves_predictions(self, tmp_path):
        groups = np.arange(len(_X)) % 4
        model = GridSearchCV(Ridge(), {"alpha": [0.1, 1.0]}, cv=GroupKFold(n_splits=2))
        model.fit(_X, _Y_REGRESSION, groups=groups)

        loaded = _validate_and_load(tmp_path, model)

        np.testing.assert_array_equal(loaded.predict(_X), model.predict(_X))

    @pytest.mark.parametrize(
        ("func", "inverse_func"),
        [
            (np.log1p, np.expm1),
            (np.sqrt, np.square),
            (np.cbrt, None),
            (np.absolute, None),
        ],
    )
    def test_function_transformer_with_numpy_ufunc_preserves_predictions(self, tmp_path, func, inverse_func):
        input_data = np.abs(_X)
        model = Pipeline(
            [
                ("transform", FunctionTransformer(func, inverse_func=inverse_func)),
                ("model", LinearRegression()),
            ]
        ).fit(input_data, _Y_REGRESSION)

        loaded = _validate_and_load(tmp_path, model)

        np.testing.assert_array_equal(loaded.predict(input_data), model.predict(input_data))

    def test_transformed_target_regressor_with_log_exp_preserves_predictions(self, tmp_path):
        target = np.abs(_Y_REGRESSION) + 1.0
        model = TransformedTargetRegressor(regressor=LinearRegression(), func=np.log, inverse_func=np.exp)
        model.fit(_X, target)

        loaded = _validate_and_load(tmp_path, model)

        np.testing.assert_allclose(loaded.predict(_X), model.predict(_X))

    def test_one_hot_encoder_with_numpy_dtype_preserves_transform(self, tmp_path):
        values = np.array([["a"], ["b"], ["a"]])
        encoder = OneHotEncoder(dtype=np.int64, sparse_output=False).fit(values)

        loaded = _validate_and_load(tmp_path, encoder)

        assert loaded.dtype is np.int64
        np.testing.assert_array_equal(loaded.transform(values), encoder.transform(values))

    @pytest.mark.parametrize(
        "factory",
        [
            lambda: OneHotEncoder(dtype=bool, sparse_output=False),
            lambda: OneHotEncoder(dtype=np.int8, sparse_output=False),
            lambda: OrdinalEncoder(dtype=float),
            lambda: OrdinalEncoder(dtype=np.float16),
        ],
    )
    def test_encoder_with_plain_or_numpy_scalar_dtype_preserves_transform(self, tmp_path, factory):
        values = np.array([["a"], ["b"], ["a"]])
        encoder = factory().fit(values)

        loaded = _validate_and_load(tmp_path, encoder)

        assert loaded.dtype is encoder.dtype
        np.testing.assert_array_equal(loaded.transform(values), encoder.transform(values))

    def test_numpy_1_ufunc_reference_resolves(self, tmp_path):
        # NumPy 1.x pickles ufuncs under numpy.core._multiarray_umath.
        loaded = _validate_and_load_bytes(tmp_path, b"cnumpy.core._multiarray_umath\nlog1p\n.")

        assert loaded is np.log1p

    @pytest.mark.parametrize(
        "name",
        [
            "Categorical",
            "CategoricalDtype",
            "DataFrame",
            "DatetimeIndex",
            "DatetimeTZDtype",
            "Index",
            "RangeIndex",
            "Series",
            "StringDtype",
        ],
    )
    def test_pandas_3_public_alias_resolves(self, tmp_path, name):
        loaded = _validate_and_load_bytes(tmp_path, f"cpandas\n{name}\n.".encode())

        assert loaded is getattr(pd, name)

    def test_v2_payload_with_common_metadata_roundtrips(self, tmp_path):
        random_generator = np.random.default_rng(66748)
        payload = {
            "model": _fit(LinearRegression, _Y_REGRESSION),
            "metadata": {
                "created_at": datetime(2026, 10, 15, 12, 30),
                "frame": _X_FRAME.head(2),
                "groups": defaultdict(list, {"route": [713]}),
                "random_generator": random_generator,
                "series": pd.Series(["north", "south"], name="region"),
                "timestamp": pd.Timestamp("2026-10-15T12:30:00Z"),
                "timestamps": pd.date_range("2026-10-15", periods=2, tz="UTC"),
                "categories": pd.Categorical(["hourly", "session"]),
            },
            "version": "v2.0",
        }

        loaded = _validate_and_load(tmp_path, payload)

        assert loaded["version"] == payload["version"]
        assert loaded["metadata"]["created_at"] == payload["metadata"]["created_at"]
        assert loaded["metadata"]["groups"] == payload["metadata"]["groups"]
        assert loaded["metadata"]["timestamp"] == payload["metadata"]["timestamp"]
        pd.testing.assert_series_equal(loaded["metadata"]["series"], payload["metadata"]["series"])
        pd.testing.assert_index_equal(loaded["metadata"]["timestamps"], payload["metadata"]["timestamps"])
        assert loaded["metadata"]["categories"].equals(payload["metadata"]["categories"])
        pd.testing.assert_frame_equal(loaded["metadata"]["frame"], payload["metadata"]["frame"])
        assert loaded["metadata"]["random_generator"].random() == random_generator.random()


class TestModelManagerValidation:
    @pytest.mark.asyncio
    async def test_validation_runs_off_event_loop(self, monkeypatch):
        from app.core.utils import model_validator

        event_loop_thread = threading.get_ident()
        validation_threads = []

        def validate(_pkl_file):
            validation_threads.append(threading.get_ident())
            return True, None

        monkeypatch.setattr(model_validator, "validate_pickle_file_safe", validate)

        await MLModelManager()._validate_model_safe("model.pkl")

        assert validation_threads
        assert validation_threads[0] != event_loop_thread

    @pytest.mark.asyncio
    async def test_rewritten_file_at_same_path_is_rescanned(self, tmp_path, monkeypatch):
        from app.core.utils import model_validator

        pickle_file = tmp_path / "model.pkl"
        scanned = []
        real_validate = model_validator.validate_pickle_file_safe

        def validate(pkl_file):
            scanned.append(pkl_file)
            return real_validate(pkl_file)

        monkeypatch.setattr(model_validator, "validate_pickle_file_safe", validate)
        manager = MLModelManager()
        manager._validated_files.pop(str(pickle_file), None)

        pickle_file.write_bytes(pickle.dumps({"version": "v1"}))
        assert await manager._load_model_from_file(str(pickle_file)) == {"version": "v1"}
        assert await manager._load_model_from_file(str(pickle_file)) == {"version": "v1"}
        assert len(scanned) == 1

        # A stale reload or retrain rewrites the same path with new bytes.
        pickle_file.write_bytes(pickle.dumps({"version": "v2", "retrained": True}))
        assert (await manager._load_model_from_file(str(pickle_file)))["version"] == "v2"
        assert len(scanned) == 2


class TestTrainModelPayload:
    @pytest.mark.parametrize("model_type", sorted(_REGRESSORS))
    def test_regressor_payload_preserves_predictions(self, tmp_path, model_type):
        model = _fit(_REGRESSORS[model_type], _Y_REGRESSION)
        payload = {"model": model, "metadata": {"feature_columns": ["a", "b", "c", "d"]}, "version": "v2.0"}

        loaded = _validate_and_load(tmp_path, payload)

        assert type(loaded["model"]) is type(model)
        assert loaded["metadata"] == payload["metadata"]
        assert loaded["version"] == "v2.0"
        np.testing.assert_array_equal(loaded["model"].predict(_X), model.predict(_X))

    @pytest.mark.parametrize("protocol", [3, 4, pickle.HIGHEST_PROTOCOL])
    @pytest.mark.parametrize("variant", sorted(_PARAMETER_VARIANTS))
    def test_supported_parameter_variant_preserves_predictions(self, tmp_path, protocol, variant):
        factory, target = _PARAMETER_VARIANTS[variant]
        model = _fit(factory, target)

        loaded = _validate_and_load(tmp_path, model, protocol=protocol)

        assert type(loaded) is type(model)
        np.testing.assert_array_equal(loaded.predict(_X), model.predict(_X))

    @pytest.mark.parametrize("protocol", [4, pickle.HIGHEST_PROTOCOL])
    def test_search_space_combination_preserves_predictions(self, tmp_path, search_space_model, protocol):
        payload = {
            "model": search_space_model,
            "metadata": {"feature_columns": list(_X_FRAME.columns)},
            "version": "v2.0",
        }

        loaded = _validate_and_load(tmp_path, payload, protocol=protocol)

        assert type(loaded["model"]) is type(search_space_model)
        np.testing.assert_array_equal(loaded["model"].predict(_X_FRAME), search_space_model.predict(_X_FRAME))

    @pytest.mark.parametrize("model_type", sorted(_CLASSIFIERS))
    def test_classifier_payload_preserves_predictions(self, tmp_path, model_type):
        model = _fit(_CLASSIFIERS[model_type], _Y_CLASSIFICATION)
        payload = {"model": model, "metadata": {"feature_columns": ["a", "b", "c", "d"]}, "version": "v2.0"}

        loaded = _validate_and_load(tmp_path, payload)

        assert type(loaded["model"]) is type(model)
        np.testing.assert_array_equal(loaded["model"].predict(_X), model.predict(_X))

    @pytest.mark.parametrize("step", sorted(_PIPELINE_STEPS))
    def test_pipeline_payload_preserves_predictions(self, tmp_path, step):
        model = _fit(
            lambda: Pipeline([(step, _PIPELINE_STEPS[step]()), ("model", LinearRegression())]),
            _Y_REGRESSION,
        )

        loaded = _validate_and_load(tmp_path, {"model": model, "metadata": {}, "version": "v2.0"})

        np.testing.assert_array_equal(loaded["model"].predict(_X), model.predict(_X))


@pytest.mark.skipif(xgb is None, reason="XGBoost is not installed")
class TestLegacyRawModel:
    """Raw models pickled directly, as the local PBP fixtures are (XGBRegressor, protocol 4)."""

    @pytest.mark.parametrize("protocol", [3, 4, pickle.HIGHEST_PROTOCOL])
    def test_raw_xgboost_regressor_preserves_predictions(self, tmp_path, protocol):
        model = _fit(_REGRESSORS["xgboost"], _Y_REGRESSION)

        loaded = _validate_and_load(tmp_path, model, protocol=protocol)

        assert isinstance(loaded, xgb.XGBRegressor)
        np.testing.assert_array_equal(loaded.predict(_X), model.predict(_X))

    def test_raw_xgboost_classifier_preserves_predictions(self, tmp_path):
        model = _fit(_CLASSIFIERS["xgboost"], _Y_CLASSIFICATION)

        loaded = _validate_and_load(tmp_path, model, protocol=4)

        assert isinstance(loaded, xgb.XGBClassifier)
        np.testing.assert_array_equal(loaded.predict(_X), model.predict(_X))
        np.testing.assert_array_equal(loaded.predict_proba(_X), model.predict_proba(_X))

    def test_raw_model_loads_through_model_manager(self, tmp_path):
        model = _fit(_REGRESSORS["xgboost"], _Y_REGRESSION)
        pickle_file = tmp_path / "hourly_revenue_fixture.pkl"
        pickle_file.write_bytes(pickle.dumps(model, protocol=4))

        is_valid, error = validate_pickle_file_safe(str(pickle_file))
        normalized = MLModelManager._normalize_loaded_model(_load_pickle_sync(str(pickle_file)))

        assert is_valid is True, error
        assert set(normalized) == {"model"}
        np.testing.assert_array_equal(normalized["model"].predict(_X), model.predict(_X))

    def test_payload_loads_through_model_manager(self, tmp_path):
        model = _fit(_REGRESSORS["xgboost"], _Y_REGRESSION)
        pickle_file = tmp_path / "Train_Model_fixture_v2.0.pkl"
        pickle_file.write_bytes(pickle.dumps({"model": model, "metadata": {"target": "y"}, "version": "v2.0"}))

        is_valid, error = validate_pickle_file_safe(str(pickle_file))
        normalized = MLModelManager._normalize_loaded_model(_load_pickle_sync(str(pickle_file)))

        assert is_valid is True, error
        assert normalized["metadata"] == {"target": "y"}
        assert normalized["version"] == "v2.0"
        np.testing.assert_array_equal(normalized["model"].predict(_X), model.predict(_X))
