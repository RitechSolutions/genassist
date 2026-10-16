"""
Restricted pickle unpickler for ML model loading.

Standard ``pickle.load`` executes arbitrary code via ``__reduce__``.
This module provides a restricted unpickler that only allows exact globals
required by supported NumPy and ML-framework artifacts.

Usage::

    from app.core.utils.safe_pickle import safe_pickle_load

    with open("model.pkl", "rb") as f:
        model = safe_pickle_load(f)
"""

from __future__ import annotations

import pickle
from collections.abc import Set as SetABC
from typing import AbstractSet, Any, BinaryIO, Mapping

# ---------------------------------------------------------------------------
# Exact module + global allowlist
# ---------------------------------------------------------------------------
# Every entry is an exact ``(module, name)`` pair needed by supported model
# artifacts. Wildcards and module-prefix matching are intentionally forbidden:
# framework packages expose file, process, and code-execution helpers too.
# ---------------------------------------------------------------------------

# Element-wise ufuncs commonly wrapped by FunctionTransformer and
# TransformedTargetRegressor. NumPy 2 pickles them as ``numpy.<name>``;
# NumPy 1.x as ``numpy.core._multiarray_umath.<name>``.
_ALLOWED_UFUNCS = {"absolute", "cbrt", "exp", "expm1", "log", "log1p", "sqrt", "square"}

_ALLOWED_GLOBALS: dict[str, set[str]] = {
    "_codecs": {"encode"},
    "builtins": {
        "bool",
        "bytearray",
        "bytes",
        "complex",
        "float",
        "frozenset",
        "int",
        "list",
        "object",
        "set",
        "slice",
        "str",
    },
    "collections": {"OrderedDict", "defaultdict"},
    "copyreg": {"_reconstructor"},
    "datetime": {"date", "datetime", "time", "timedelta", "timezone"},
    "numpy": {
        "dtype",
        "ndarray",
        # Scalar types, e.g. an estimator's ``dtype=np.int8`` parameter.
        "bool_",
        "bytes_",
        "complex64",
        "complex128",
        "datetime64",
        "float16",
        "float32",
        "float64",
        "int8",
        "int16",
        "int32",
        "int64",
        "str_",
        "timedelta64",
        "uint8",
        "uint16",
        "uint32",
        "uint64",
        *_ALLOWED_UFUNCS,
    },
    "numpy._core._multiarray_umath": set(_ALLOWED_UFUNCS),
    "numpy.core._multiarray_umath": set(_ALLOWED_UFUNCS),
    "numpy._core.multiarray": {"_reconstruct", "scalar"},
    "numpy._core.numeric": {"_frombuffer"},
    "numpy.core.multiarray": {"_reconstruct", "scalar"},
    "numpy.core.numeric": {"_frombuffer"},
    "numpy.ma": {"MaskedArray"},
    # NumPy 2 pickles MaskedArray as numpy.ma.MaskedArray; NumPy 1.x as numpy.ma.core.
    "numpy.ma.core": {"MaskedArray", "_mareconstruct"},
    "numpy.random._mt19937": {"MT19937"},
    "numpy.random._pcg64": {"PCG64"},
    "numpy.random._philox": {"Philox"},
    "numpy.random._pickle": {"__bit_generator_ctor", "__generator_ctor", "__randomstate_ctor"},
    "numpy.random._sfc64": {"SFC64"},
    "numpy.random.bit_generator": {"SeedSequence", "__pyx_unpickle_SeedSequence"},
    # Pandas 3 pickles public types through top-level aliases while pandas 2
    # uses the internal module paths retained below.
    "pandas": {
        "Categorical",
        "CategoricalDtype",
        "DataFrame",
        "DatetimeIndex",
        "DatetimeTZDtype",
        "Index",
        "RangeIndex",
        "Series",
        "StringDtype",
    },
    "pandas._libs.arrays": {"__pyx_unpickle_NDArrayBacked"},
    "pandas._libs.internals": {"_unpickle_block"},
    "pandas._libs.tslibs.offsets": {"Day"},
    "pandas._libs.tslibs.timedeltas": {"_timedelta_unpickle"},
    "pandas._libs.tslibs.timestamps": {"_unpickle_timestamp"},
    "pandas.arrays": {"DatetimeArray", "StringArray"},
    "pandas.core.arrays.categorical": {"Categorical"},
    "pandas.core.arrays.datetimes": {"DatetimeArray"},
    "pandas.core.dtypes.dtypes": {"CategoricalDtype", "DatetimeTZDtype"},
    "pandas.core.frame": {"DataFrame"},
    "pandas.core.indexes.base": {"Index", "_new_Index"},
    "pandas.core.indexes.datetimes": {"DatetimeIndex", "_new_DatetimeIndex"},
    "pandas.core.indexes.range": {"RangeIndex"},
    "pandas.core.internals.managers": {"BlockManager", "SingleBlockManager"},
    "pandas.core.series": {"Series"},
    "sklearn._loss._loss": {
        "CyAbsoluteError",
        "CyExponentialLoss",
        "CyHalfBinomialLoss",
        "CyHalfMultinomialLoss",
        "CyHalfSquaredError",
        "CyHuberLoss",
        "CyPinballLoss",
        "__pyx_unpickle_CyHalfMultinomialLoss",
    },
    "sklearn._loss.link": {"HalfLogitLink", "IdentityLink", "Interval", "LogitLink", "MultinomialLogit"},
    "sklearn._loss.loss": {
        "AbsoluteError",
        "ExponentialLoss",
        "HalfBinomialLoss",
        "HalfMultinomialLoss",
        "HalfSquaredError",
        "HuberLoss",
        "PinballLoss",
    },
    "sklearn.cluster._kmeans": {"KMeans"},
    "sklearn.compose._column_transformer": {"ColumnTransformer"},
    "sklearn.compose._target": {"TransformedTargetRegressor"},
    "sklearn.decomposition._pca": {"PCA"},
    "sklearn.dummy": {"DummyClassifier", "DummyRegressor"},
    "sklearn.ensemble._forest": {
        "ExtraTreesClassifier",
        "ExtraTreesRegressor",
        "RandomForestClassifier",
        "RandomForestRegressor",
    },
    "sklearn.ensemble._gb": {"GradientBoostingClassifier", "GradientBoostingRegressor"},
    "sklearn.ensemble._hist_gradient_boosting.binning": {"_BinMapper"},
    "sklearn.ensemble._hist_gradient_boosting.gradient_boosting": {
        "HistGradientBoostingClassifier",
        "HistGradientBoostingRegressor",
    },
    "sklearn.ensemble._hist_gradient_boosting.predictor": {"TreePredictor"},
    "sklearn.ensemble._iforest": {"IsolationForest"},
    "sklearn.impute._base": {"SimpleImputer"},
    "sklearn.linear_model._base": {"LinearRegression"},
    "sklearn.linear_model._coordinate_descent": {"ElasticNet", "Lasso"},
    "sklearn.linear_model._logistic": {"LogisticRegression"},
    "sklearn.linear_model._ridge": {"Ridge"},
    "sklearn.linear_model._sgd_fast": {"Hinge"},
    "sklearn.linear_model._stochastic_gradient": {"SGDClassifier", "SGDRegressor"},
    "sklearn.metrics._dist_metrics": {
        "BrayCurtisDistance32",
        "BrayCurtisDistance64",
        "CanberraDistance32",
        "CanberraDistance64",
        "ChebyshevDistance32",
        "ChebyshevDistance64",
        "DiceDistance32",
        "DiceDistance64",
        "EuclideanDistance32",
        "EuclideanDistance64",
        "HammingDistance32",
        "HammingDistance64",
        "HaversineDistance32",
        "HaversineDistance64",
        "JaccardDistance32",
        "JaccardDistance64",
        "KulsinskiDistance32",
        "KulsinskiDistance64",
        "MahalanobisDistance32",
        "MahalanobisDistance64",
        "ManhattanDistance32",
        "ManhattanDistance64",
        "MatchingDistance32",
        "MatchingDistance64",
        "MinkowskiDistance32",
        "MinkowskiDistance64",
        "RogersTanimotoDistance32",
        "RogersTanimotoDistance64",
        "RussellRaoDistance32",
        "RussellRaoDistance64",
        "SEuclideanDistance32",
        "SEuclideanDistance64",
        "SokalMichenerDistance32",
        "SokalMichenerDistance64",
        "SokalSneathDistance32",
        "SokalSneathDistance64",
        "newObj",
    },
    "sklearn.metrics._classification": {"accuracy_score"},
    "sklearn.metrics._regression": {"r2_score"},
    "sklearn.neighbors._ball_tree": {"BallTree", "newObj"},
    "sklearn.neighbors._classification": {"KNeighborsClassifier"},
    "sklearn.neighbors._kd_tree": {"KDTree", "newObj"},
    "sklearn.neighbors._regression": {"KNeighborsRegressor"},
    "sklearn.neural_network._multilayer_perceptron": {"MLPClassifier", "MLPRegressor"},
    "sklearn.neural_network._stochastic_optimizers": {"AdamOptimizer", "SGDOptimizer"},
    "sklearn.metrics._scorer": {"_PassthroughScorer", "_Scorer"},
    "sklearn.model_selection._search": {"GridSearchCV"},
    "sklearn.model_selection._split": {
        "GroupKFold",
        "KFold",
        "RepeatedKFold",
        "RepeatedStratifiedKFold",
        "ShuffleSplit",
        "StratifiedKFold",
        "StratifiedShuffleSplit",
        "TimeSeriesSplit",
    },
    "sklearn.pipeline": {"Pipeline"},
    "sklearn.preprocessing._data": {
        "MaxAbsScaler",
        "MinMaxScaler",
        "PowerTransformer",
        "QuantileTransformer",
        "RobustScaler",
        "StandardScaler",
    },
    "sklearn.preprocessing._encoders": {"OneHotEncoder", "OrdinalEncoder"},
    "sklearn.preprocessing._function_transformer": {"FunctionTransformer"},
    "sklearn.preprocessing._label": {"LabelBinarizer", "LabelEncoder"},
    "sklearn.preprocessing._polynomial": {"PolynomialFeatures"},
    "sklearn.svm._classes": {"SVC", "SVR"},
    "sklearn.tree._classes": {
        "DecisionTreeClassifier",
        "DecisionTreeRegressor",
        "ExtraTreeClassifier",
        "ExtraTreeRegressor",
    },
    "sklearn.tree._tree": {"Tree"},
    "sklearn.utils._metadata_requests": {"MetadataRequest", "MethodMetadataRequest"},
    "xgboost.core": {"Booster"},
    "xgboost.sklearn": {"XGBClassifier", "XGBRegressor"},
    "lightgbm.basic": {"Booster"},
    "lightgbm.sklearn": {"LGBMClassifier", "LGBMRegressor"},
    "catboost.core": {"CatBoostClassifier", "CatBoostRegressor"},
}

_PICKLE_MODULE_ALIASES = {
    "__builtin__": "builtins",
    "_loss": "sklearn._loss._loss",
    "copy_reg": "copyreg",
}

# Plain-data allowlist for caches that only hold builtins
BUILTINS_ONLY_ALLOWED_MODULES: dict[str, set[str]] = {
    "builtins": {"dict", "list", "tuple", "set", "frozenset", "int", "float", "bool", "str", "bytes", "bytearray"},
}


def _validate_allowlist(allowed_modules: Mapping[str, AbstractSet[str]]) -> None:
    for module, allowed_names in allowed_modules.items():
        if not isinstance(module, str) or not isinstance(allowed_names, SetABC):
            raise TypeError("Pickle allowlists must map module names to sets of exact global names.")
        if any(not isinstance(name, str) for name in allowed_names):
            raise TypeError("Pickle allowlist global names must be strings.")


def _resolve_pickle_module(module: str) -> str:
    return _PICKLE_MODULE_ALIASES.get(module, module)


def _select_allowlist(
    allowed_modules: Mapping[str, AbstractSet[str]] | None,
) -> Mapping[str, AbstractSet[str]]:
    if allowed_modules is None:
        return _ALLOWED_GLOBALS
    _validate_allowlist(allowed_modules)
    return allowed_modules


def _is_pickle_global_allowed(module: str, name: str, allowed_modules: Mapping[str, AbstractSet[str]]) -> bool:
    if "." in name:
        return False
    return name in allowed_modules.get(_resolve_pickle_module(module), ())


def is_pickle_global_allowed(
    module: str,
    name: str,
    *,
    allowed_modules: Mapping[str, AbstractSet[str]] | None = None,
) -> bool:
    """Return whether an exact pickle global is permitted by the selected allowlist."""
    return _is_pickle_global_allowed(module, name, _select_allowlist(allowed_modules))


class RestrictedUnpickler(pickle._Unpickler):
    """An unpickler that only resolves globals from an allowlist (default: the ML-framework list).

    Any attempt to instantiate a class from a module not in the allowlist
    raises ``pickle.UnpicklingError``, preventing ``__reduce__``-based
    code execution from crafted pickle files.
    """

    def __init__(
        self,
        file: BinaryIO,
        *,
        allowed_modules: Mapping[str, AbstractSet[str]] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(file, **kwargs)
        self._allowed_modules = _select_allowlist(allowed_modules)
        # ids of the module-level globals handed out by find_class. They are
        # shared process-wide, so BUILD must never mutate them.
        self._resolved_global_ids: set[int] = set()

    def find_class(self, module: str, name: str) -> Any:
        if not _is_pickle_global_allowed(module, name, self._allowed_modules):
            reference = f"{module}.{name}"
            raise pickle.UnpicklingError(
                f"Disallowed pickle global {reference!a}. Only supported ML framework classes are permitted."
            )

        resolved = super().find_class(_resolve_pickle_module(module), name)
        self._resolved_global_ids.add(id(resolved))
        return resolved

    def load_build(self) -> None:
        if len(self.stack) >= 2:
            target = self.stack[-2]
            if isinstance(target, type) or id(target) in self._resolved_global_ids:
                raise pickle.UnpicklingError("Pickle BUILD cannot target a class or global object.")
        super().load_build()


RestrictedUnpickler.dispatch = pickle._Unpickler.dispatch.copy()
RestrictedUnpickler.dispatch[pickle.BUILD[0]] = RestrictedUnpickler.load_build


def safe_pickle_load(
    f: BinaryIO,
    *,
    encoding: str = "ASCII",
    allowed_modules: Mapping[str, AbstractSet[str]] | None = None,
) -> Any:
    """Drop-in replacement for ``pickle.load`` that uses the restricted unpickler.

    Args:
        f: A binary file-like object positioned at the start of a pickle stream.
        encoding: Encoding for unpickling Python 2 pickles (default ``"ASCII"``).
        allowed_modules: Allowlist to enforce; ``None`` selects the ML-framework allowlist.

    Returns:
        The deserialized object.

    Raises:
        pickle.UnpicklingError: If the pickle references a disallowed module/class.
    """
    return RestrictedUnpickler(f, encoding=encoding, allowed_modules=allowed_modules).load()
