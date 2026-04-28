"""
Restricted pickle unpickler for ML model loading.

Standard ``pickle.load`` executes arbitrary code via ``__reduce__``.
This module provides a restricted unpickler that only allows classes
from a known-safe allowlist (ML frameworks, numpy, pandas, builtins).

Usage::

    from app.core.utils.safe_pickle import safe_pickle_load

    with open("model.pkl", "rb") as f:
        model = safe_pickle_load(f)
"""

from __future__ import annotations

import io
import logging
import pickle
from typing import Any, BinaryIO

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module + class allowlist
# ---------------------------------------------------------------------------
# Each key is a module name; the value is either a set of allowed class names
# or the special sentinel ``"*"`` meaning "allow every class in this module".
#
# This list covers scikit-learn, XGBoost, LightGBM, CatBoost, numpy, pandas,
# and Python builtins that commonly appear in pickled ML artefacts.
# ---------------------------------------------------------------------------

_ALLOWED_MODULES: dict[str, set[str] | str] = {
    # Python builtins & stdlib
    "builtins": {
        "dict", "list", "tuple", "set", "frozenset",
        "int", "float", "complex", "bool", "str", "bytes", "bytearray",
        "slice", "range", "type", "object", "NoneType",
        "True", "False",
    },
    "collections": {"OrderedDict", "defaultdict", "deque"},
    "copy": {"deepcopy"},
    "copyreg": {"_reconstructor"},
    "datetime": {"datetime", "date", "time", "timedelta", "timezone"},
    "decimal": {"Decimal"},
    "enum": {"Enum", "IntEnum"},
    "functools": {"partial"},
    "_codecs": {"encode"},
    "codecs": {"encode"},

    # numpy
    "numpy": "*",
    "numpy.core": "*",
    "numpy.core.multiarray": "*",
    "numpy.core.numeric": "*",
    "numpy._core": "*",
    "numpy._core.multiarray": "*",
    "numpy.ma.core": "*",
    "numpy.random": "*",
    "numpy.dtype": "*",

    # pandas
    "pandas": "*",
    "pandas.core": "*",
    "pandas.core.frame": "*",
    "pandas.core.series": "*",
    "pandas.core.indexes": "*",
    "pandas.core.indexes.base": "*",
    "pandas.core.indexes.range": "*",
    "pandas.core.internals": "*",
    "pandas.core.internals.managers": "*",
    "pandas.core.internals.blocks": "*",
    "pandas.core.arrays": "*",
    "pandas._libs": "*",
    "pandas._libs.lib": "*",
    "pandas._libs.internals": "*",
    "pandas.compat.pickle_compat": "*",

    # scikit-learn (allow all submodules)
    "sklearn": "*",
    "sklearn.base": "*",
    "sklearn.pipeline": "*",
    "sklearn.compose": "*",
    "sklearn.preprocessing": "*",
    "sklearn.impute": "*",
    "sklearn.feature_extraction": "*",
    "sklearn.feature_extraction.text": "*",
    "sklearn.feature_selection": "*",
    "sklearn.decomposition": "*",
    "sklearn.manifold": "*",
    "sklearn.cluster": "*",
    "sklearn.mixture": "*",
    "sklearn.linear_model": "*",
    "sklearn.svm": "*",
    "sklearn.tree": "*",
    "sklearn.ensemble": "*",
    "sklearn.neighbors": "*",
    "sklearn.naive_bayes": "*",
    "sklearn.neural_network": "*",
    "sklearn.metrics": "*",
    "sklearn.model_selection": "*",
    "sklearn.utils": "*",
    "sklearn.utils._tags": "*",

    # XGBoost
    "xgboost": "*",
    "xgboost.core": "*",
    "xgboost.sklearn": "*",
    "xgboost.compat": "*",

    # LightGBM
    "lightgbm": "*",
    "lightgbm.basic": "*",
    "lightgbm.sklearn": "*",

    # CatBoost
    "catboost": "*",
    "catboost.core": "*",

    # joblib internals (used when joblib.dump saves models)
    "joblib": "*",
    "joblib.numpy_pickle": "*",
    "joblib.numpy_pickle_utils": "*",
    "joblib.numpy_pickle_compat": "*",
}

# Modules that are NEVER allowed regardless of wildcards above.
_BLOCKED_MODULES: frozenset[str] = frozenset({
    "os", "posix", "nt", "posixpath", "ntpath",
    "subprocess", "shutil",
    "sys", "importlib",
    "socket", "http", "urllib", "requests",
    "ctypes", "signal",
    "code", "codeop", "compile", "compileall",
    "pickle", "shelve", "marshal",
    "webbrowser",
    "multiprocessing",
    "__builtin__", "builtins.__import__",
})


class RestrictedUnpickler(pickle.Unpickler):
    """An unpickler that only allows classes from the ML-framework allowlist.

    Any attempt to instantiate a class from a module not in the allowlist
    raises ``pickle.UnpicklingError``, preventing ``__reduce__``-based
    code execution from crafted pickle files.
    """

    def find_class(self, module: str, name: str) -> Any:
        # Explicit block check first
        top_level = module.split(".")[0]
        if module in _BLOCKED_MODULES or top_level in _BLOCKED_MODULES:
            raise pickle.UnpicklingError(
                f"Blocked: {module}.{name} — loading classes from '{module}' "
                f"is not allowed for security reasons"
            )

        # Check if the module is in the allowlist
        allowed = _ALLOWED_MODULES.get(module)
        if allowed is None:
            # Try matching the top-level package with wildcard submodules
            # e.g., "sklearn.ensemble._forest" matches if "sklearn" has "*"
            for allowed_mod, allowed_classes in _ALLOWED_MODULES.items():
                if allowed_classes == "*" and module.startswith(allowed_mod + "."):
                    return super().find_class(module, name)
                if allowed_classes == "*" and module == allowed_mod:
                    return super().find_class(module, name)

            raise pickle.UnpicklingError(
                f"Blocked: {module}.{name} — module '{module}' is not in the "
                f"allowed list for ML model loading"
            )

        # Module is in the allowlist — check class-level restriction
        if allowed == "*":
            return super().find_class(module, name)

        if name not in allowed:
            raise pickle.UnpicklingError(
                f"Blocked: {module}.{name} — class '{name}' is not allowed "
                f"from module '{module}'"
            )

        return super().find_class(module, name)


def safe_pickle_load(f: BinaryIO, *, encoding: str = "ASCII") -> Any:
    """Drop-in replacement for ``pickle.load`` that uses the restricted unpickler.

    Args:
        f: A binary file-like object positioned at the start of a pickle stream.
        encoding: Encoding for unpickling Python 2 pickles (default ``"ASCII"``).

    Returns:
        The deserialized object.

    Raises:
        pickle.UnpicklingError: If the pickle references a disallowed module/class.
    """
    return RestrictedUnpickler(f, encoding=encoding).load()
