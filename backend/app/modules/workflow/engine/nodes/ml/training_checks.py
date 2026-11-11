"""
Plain-language checks and messages for the Train Model node.

Bad data or settings used to surface as whatever pandas, scikit-learn or
XGBoost raised - type errors, sklearn parameter dumps, or an XGBoost C++
message with build-server paths. The checks here run before training and say
what is wrong in terms of the node's own fields; ``describe_training_error``
cleans up whatever library error still gets through.

``encode_target_classes`` maps classification labels (text like A/B/C or
high/low, or numbers that don't start at 0) to 0..n-1, which XGBoost requires
and which keeps every model off text targets. The labels are saved with the
model so inference can turn predictions back into them.
"""

import math
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException

# Keep in sync with frontend/src/views/AIAgents/Workflows/nodeDialogs/training/scoringOptions.ts.
CLASSIFICATION_SCORING = {
    "accuracy": "Accuracy",
    "balanced_accuracy": "Balanced accuracy",
    "f1_weighted": "F1 (weighted)",
    "f1_macro": "F1 (macro)",
    "precision_weighted": "Precision (weighted)",
    "recall_weighted": "Recall (weighted)",
    "roc_auc_ovr_weighted": "ROC AUC",
    "neg_log_loss": "Log loss",
}
REGRESSION_SCORING = {
    "r2": "R²",
    "neg_root_mean_squared_error": "RMSE",
    "neg_mean_absolute_error": "MAE",
    "neg_mean_squared_error": "MSE",
    "neg_mean_absolute_percentage_error": "MAPE",
}

# A classification target with more distinct values than this (and more than
# half the rows) is almost certainly a continuous number, not classes.
_MAX_CLASSES_BEFORE_SUSPECT = 20

_MAX_LISTED = 5
_MAX_VALUE_LENGTH = 80

# Missing Value Handling strategies that cope with a column that has no values.
EMPTY_COLUMN_STRATEGIES = frozenset({"drop_column", "impute_constant"})

# Keep in sync with frontend/src/constants/mlModelTypes.ts.
MODEL_LABELS = {
    "xgboost": "XGBoost",
    "lightgbm": "LightGBM",
    "catboost": "CatBoost",
    "random_forest": "Random Forest",
    "extra_trees": "Extra Trees",
    "gradient_boosting": "Gradient Boosting",
    "decision_tree": "Decision Tree",
    "linear_regression": "Linear Regression",
    "ridge_regression": "Ridge Regression",
    "lasso_regression": "Lasso Regression",
    "elastic_net": "Elastic Net",
    "logistic_regression": "Logistic Regression",
    "svm": "Support Vector Machine",
    "knn": "K-Nearest Neighbors",
    "neural_network": "Neural Network",
}


def model_label(model_type: str) -> str:
    return MODEL_LABELS.get(model_type, model_type)


def _fail(message: str) -> None:
    raise AppException(error_key=ErrorKey.INTERNAL_ERROR, error_detail=message)


def format_value(value: Any) -> str:
    """Show a value the way a user would write it: 49 not np.float64(49.0)."""
    if isinstance(value, np.generic):
        value = value.item()
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "empty"
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, float):
        if math.isinf(value):
            return "infinity" if value > 0 else "-infinity"
        if value.is_integer() and abs(value) < 1e15:
            return str(int(value))
        return f"{value:.6g}"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    text = str(value)
    if len(text) > _MAX_VALUE_LENGTH:
        text = text[: _MAX_VALUE_LENGTH - 1] + "…"
    return f"'{text}'"


def _format_list(values: Sequence[Any]) -> str:
    shown = ", ".join(format_value(v) for v in list(values)[:_MAX_LISTED])
    return shown + (", ..." if len(values) > _MAX_LISTED else "")


def _format_names(names: Sequence[Any], quote: bool = True) -> str:
    shown = [f"'{n}'" if quote else str(n) for n in list(names)[:_MAX_LISTED]]
    more = len(names) - len(shown)
    return ", ".join(shown) + (f" and {more} more" if more > 0 else "")


def _as_positive_int(value: Any, field: str, minimum: int = 1) -> int:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = float("nan")
    if math.isnan(number) or not number.is_integer() or number < minimum:
        _fail(f"{field} must be a whole number of {minimum} or more - got {format_value(value)}.")
    return int(number)


def check_validation_split(value: Any) -> float:
    """Validation Split as a float in [0, 1) - 0 trains on every row."""
    try:
        split = float(value)
    except (TypeError, ValueError):
        split = float("nan")
    if math.isnan(split) or split < 0 or split >= 1:
        _fail(
            "Validation Split must be a fraction from 0 up to (not including) 1, e.g. 0.2 "
            f"for 20% - got {format_value(value)}."
        )
    return split


def check_columns(target_column: str, feature_columns: List[str]) -> None:
    if target_column in feature_columns:
        _fail(
            f"Target column '{target_column}' is also selected as a feature column, so the "
            "model would be given the answer. Remove it from Feature Columns."
        )


def check_optimization_config(method: str, opt_config: Dict[str, Any]) -> Dict[str, Any]:
    """Validate and normalize search settings before any data is loaded."""
    if method == "none":
        return opt_config
    config = dict(opt_config)
    scoring = config.get("scoring")
    if isinstance(scoring, str):
        scoring = scoring.strip()
    if scoring and str(scoring).lower() != "auto":
        # The dropdown offers the metrics above; any other scikit-learn scorer
        # typed into the old free-text field keeps working.
        from sklearn.metrics import get_scorer_names

        if scoring not in CLASSIFICATION_SCORING and scoring not in REGRESSION_SCORING and (
            scoring not in get_scorer_names()
        ):
            known = {**CLASSIFICATION_SCORING, **REGRESSION_SCORING}
            _fail(
                f"Scoring '{scoring}' is not supported. Choose one of: "
                f"{', '.join(known.values())} - or leave it on Auto."
            )
        config["scoring"] = scoring
    else:
        config.pop("scoring", None)
    for key in ("cvFolds", "nIter", "nTrials", "gridPoints", "randomPoints"):
        if config.get(key) in (None, ""):
            config.pop(key, None)
    if config.get("cvFolds") is not None:
        config["cvFolds"] = _as_positive_int(config["cvFolds"], "CV Folds", minimum=2)
    for key, field in (
        ("nIter", "Iterations"),
        ("nTrials", "Trials"),
        ("gridPoints", "Grid Points"),
        ("randomPoints", "Random Points"),
    ):
        if config.get(key) is not None:
            config[key] = _as_positive_int(
                config[key], field, minimum=2 if key in ("gridPoints", "randomPoints") else 1
            )
    if config.get("timeoutSeconds") not in (None, ""):
        config["timeoutSeconds"] = _as_positive_int(config["timeoutSeconds"], "Timeout (seconds)")
    else:
        config.pop("timeoutSeconds", None)
    return config


# Scorers that need predict_proba; SVC only has it with probability=True.
_PROBABILITY_SCORING = {"roc_auc_ovr_weighted", "neg_log_loss"}


def check_search_against_data(
    opt_config: Dict[str, Any],
    is_classification: bool,
    training_rows: int,
    is_time_based: bool,
    model_type: str = "",
    model_parameters: Optional[Dict[str, Any]] = None,
) -> None:
    """Checks that need the task and the size of the training split."""
    scoring = opt_config.get("scoring")
    if (
        scoring in _PROBABILITY_SCORING
        and model_type == "svm"
        and is_classification
        and not (model_parameters or {}).get("probability")
    ):
        _fail(
            f"Scoring '{CLASSIFICATION_SCORING[scoring]}' needs class probabilities, which Support "
            "Vector Machine only gives with probability set to true in Model Parameters. Add "
            '"probability": true there, or choose another Scoring metric.'
        )
    if scoring:
        if is_classification and scoring in REGRESSION_SCORING:
            _fail(
                f"Scoring '{REGRESSION_SCORING[scoring]}' is a regression metric, but this model is "
                f"trained for classification. Choose one of: {', '.join(CLASSIFICATION_SCORING.values())}."
            )
        if not is_classification and scoring in CLASSIFICATION_SCORING:
            _fail(
                f"Scoring '{CLASSIFICATION_SCORING[scoring]}' is a classification metric, but this model "
                f"is trained for regression. Choose one of: {', '.join(REGRESSION_SCORING.values())}."
            )
    cv_folds = int(opt_config.get("cvFolds", 3))
    # TimeSeriesSplit needs one more row than folds; KFold needs one row per fold.
    needed = cv_folds + 1 if is_time_based else cv_folds
    if training_rows < needed:
        _fail(
            f"CV Folds is {cv_folds}, but the training split has only {training_rows} row(s). "
            f"Lower CV Folds or use more data."
        )


def check_training_data(
    X: pd.DataFrame,
    y: pd.Series,
    target_column: str,
    is_classification: bool,
    model_name: str,
    missing_value_strategies: Optional[Dict[str, Any]] = None,
) -> None:
    """Data problems that would otherwise fail deep inside a library."""
    if len(y) == 0:
        _fail(f"Target column '{target_column}' has no values, so there is nothing to train on.")
    if len(y) < 2:
        _fail(f"Training needs at least 2 rows with a value in '{target_column}' - found {len(y)}.")

    strategies = missing_value_strategies or {}
    # Missing Value Handling drops or fills these on purpose.
    empty_columns = [
        c for c in X.columns
        if strategies.get(c) not in EMPTY_COLUMN_STRATEGIES and X[c].isna().all()
    ]
    if empty_columns:
        _fail(
            f"Feature column(s) {_format_names(empty_columns)} have no values. "
            "Remove them from Feature Columns."
        )

    infinite = []
    for name, series in [*X.items(), (target_column, y)]:
        # Filling only replaces empty values; a dropped column never reaches a model.
        if strategies.get(name) == "drop_column":
            continue
        if pd.api.types.is_numeric_dtype(series) and not pd.api.types.is_bool_dtype(series):
            count = int(np.isinf(series.to_numpy(dtype=float, na_value=np.nan)).sum())
            if count:
                infinite.append(f"'{name}' ({count} row(s))")
    if infinite:
        _fail(
            f"Column(s) {_format_names(infinite, quote=False)} contain infinite values (inf), which no model can "
            "train on. Remove those rows or replace the values in the source data."
        )

    if is_classification:
        classes = y.unique()
        if len(classes) < 2:
            _fail(
                f"Target column '{target_column}' has only one class ({_format_list(classes)}). "
                "A classification model needs at least two different values to learn from."
            )
        if (
            pd.api.types.is_float_dtype(y)
            and not np.all(np.mod(y.to_numpy(dtype=float), 1) == 0)
            and len(classes) > _MAX_CLASSES_BEFORE_SUSPECT
            and len(classes) > len(y) / 2
        ):
            _fail(
                f"Target column '{target_column}' holds decimal numbers with {len(classes)} different "
                f"values (e.g. {_format_list(classes)}), so it can't be used as classes for "
                f"{model_name}. Set Task Type to Regression, or choose a regression model."
            )
    elif not pd.api.types.is_numeric_dtype(y):
        sample = [v for v in y.unique() if not _is_number(v)]
        _fail(
            f"Target column '{target_column}' has text values (e.g. {_format_list(sample)}), but "
            f"{model_name} is set to predict a number (regression). Choose a numeric target column, "
            "or set Task Type to Classification with a model that supports it."
        )


def numeric_target(y: pd.Series) -> pd.Series:
    """A text column holding only numbers ('12.5', '3') as floats; anything else unchanged."""
    if pd.api.types.is_numeric_dtype(y) or pd.api.types.is_bool_dtype(y):
        return y
    converted = pd.to_numeric(y, errors="coerce")
    return converted if converted.notna().sum() == y.notna().sum() else y


def _is_number(value: Any) -> bool:
    try:
        float(value)
        return True
    except (TypeError, ValueError):
        return False


def check_training_classes(y_train: pd.Series, target_column: str) -> None:
    """After the split and row removal the training rows must still hold 2+ classes."""
    classes = pd.unique(y_train)
    if len(classes) < 2:
        _fail(
            f"After the validation split and row filtering, the training rows of '{target_column}' "
            f"hold only one class ({_format_list(classes)}). Use more data, a smaller Validation "
            "Split, or a random split, or relax Outlier / Missing Value Handling that removes rows."
        )


def _native(value: Any) -> Any:
    return value.item() if isinstance(value, np.generic) else value


def _storable_label(value: Any) -> Any:
    """A label as a plain Python value that is safe to save in the model artifact."""
    value = _native(value)
    if isinstance(value, (pd.Timestamp, pd.Timedelta)):
        return value.isoformat()
    return value


def encode_target_classes(
    y_train: pd.Series, y_val: Optional[pd.Series] = None
) -> Tuple[pd.Series, Optional[pd.Series], List[Any]]:
    """
    Codes 0..n-1 for the classes in the training rows, plus the labels in code
    order. Validation rows get the same codes, or -1 for a class training
    never saw.
    """
    categories = pd.Index(pd.unique(y_train))
    try:
        categories = categories.sort_values()
    except TypeError:
        categories = pd.Index(sorted(categories, key=str), dtype=object)

    def codes(series: pd.Series) -> pd.Series:
        return pd.Series(
            pd.Categorical(series, categories=categories).codes, index=series.index, dtype="int64"
        )

    labels = [_storable_label(value) for value in categories.tolist()]
    return codes(y_train), codes(y_val) if y_val is not None else None, labels


def _label_key(value: Any) -> str:
    """Compare labels the way a user types them: 1, 1.0 and "1" are the same class."""
    value = _native(value)
    if isinstance(value, bool):
        return str(value)
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if number.is_integer():
        return str(int(number))
    return repr(number)


def remap_class_weight(params: Dict[str, Any], labels: Sequence[Any]) -> Dict[str, Any]:
    """
    Model Parameters that name classes by the user's labels, re-keyed to the
    class codes the model is fit on: scikit-learn's class_weight and
    CatBoost's class_weights / class_names.
    """
    by_label = {_label_key(label): code for code, label in enumerate(labels)}

    def code_for(name: str, value: Any) -> int:
        code = by_label.get(_label_key(value))
        if code is None:
            _fail(
                f"Model Parameters: {name} has a class {format_value(value)} that is not in the "
                f"training data. Classes are: {_format_list(labels)}."
            )
        return code

    remapped = dict(params)
    for name in ("class_weight", "class_weights"):
        weights = params.get(name)
        if isinstance(weights, dict):
            remapped[name] = {code_for(name, key): weight for key, weight in weights.items()}
    if isinstance(params.get("class_names"), list):
        remapped["class_names"] = [code_for("class_names", value) for value in params["class_names"]]
    return remapped


def decode_target_classes(predictions: np.ndarray, labels: Sequence[Any]) -> np.ndarray:
    """Turn encoded class predictions back into the labels the model was trained on."""
    raw = np.asarray(predictions).ravel()
    try:
        numeric = raw.astype(float)
    except (TypeError, ValueError) as e:
        raise ValueError(f"Model predicted values that are not class codes: {raw[:3].tolist()}") from e
    codes = numeric.astype(int)
    bad = (codes != numeric) | (codes < 0) | (codes >= len(labels))
    if bad.any():
        raise ValueError(
            f"Model predicted class code {raw[bad][0]!s}, which is not one of its {len(labels)} classes"
        )
    return np.asarray(list(labels), dtype=object)[codes]


# "[10:27:26] /path/to/src/data/gradient_index.h:99: " in front of XGBoost errors.
_XGBOOST_PREFIX = re.compile(r"\[\d{2}:\d{2}:\d{2}\]\s+\S+:\d+:\s*")
# An absolute path ("/app/datavolume/ml_models/<thread>/x.pkl") - not a date
# like 2024/01/15, a unit like km/h or a URL, which never start with a lone "/".
_FILE_PATH = re.compile(
    r"(?<![\w:/.])(?:/[\w.\-+@<>]+){2,}(?::\d+)?"  # /app/datavolume/x.pkl
    r"|(?<![\w:/])\.{1,2}(?:/[\w.\-+@<>]+)+(?::\d+)?"  # ./app/x.py:12
    r"|(?<![\w:/.])[\w.\-+]+(?:/[\w.\-+]+)+\.[A-Za-z][\w]{0,9}\b(?::\d+)?"  # datavolume/m/x.pkl
)

_XGBOOST_TYPES = {"int": "a whole number", "float": "a number", "bool": "true or false"}

_PARAM_PATTERNS = [
    (
        re.compile(r"__init__\(\) got an unexpected keyword argument '(?P<p>[^']+)'"),
        lambda m, model: (
            f"Model Parameters: '{m['p']}' is not a setting of {model}. "
            "Remove it or check the spelling."
        ),
    ),
    (
        re.compile(r"The '(?P<p>[^']+)' parameter of \w+ must be (?P<rule>.+?)\. Got (?P<got>.+?) instead\."),
        lambda m, model: f"Model Parameters: '{m['p']}' must be {m['rule']} - got {m['got']}.",
    ),
    (
        re.compile(r"Invalid Parameter format for (?P<p>\w+) expect (?P<t>\w+) but value='(?P<v>[^']*)'"),
        lambda m, model: (
            f"Model Parameters: '{m['p']}' must be "
            f"{_XGBOOST_TYPES.get(m['t'], 'a ' + m['t'])} - got '{m['v']}'."
        ),
    ),
    (
        re.compile(r"value (?P<v>\S+) for Parameter (?P<p>\w+) should be (?P<rule>.+?)(?:\s*$|\n)"),
        lambda m, model: f"Model Parameters: '{m['p']}' should be {m['rule'].rstrip('.')} - got {m['v']}.",
    ),
]


def describe_training_error(error: BaseException, model_name: str) -> str:
    """A library error as one readable line: no C++ stack trace, no server paths."""
    text = str(error) or type(error).__name__
    text = text.split("Stack trace:", 1)[0]
    text = _XGBOOST_PREFIX.sub("", text)
    text = text.replace("Check failed: valid: ", "")
    for pattern, render in _PARAM_PATTERNS:
        match = pattern.search(text)
        if match:
            text = render(match, model_name)
            break
    text = _FILE_PATH.sub("<path>", text)
    text = " ".join(text.split())
    return text if len(text) <= 500 else text[:499] + "…"

