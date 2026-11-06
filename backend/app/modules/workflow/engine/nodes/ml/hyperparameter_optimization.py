"""
Hyperparameter optimization for the Train Model node.

Supports three search methods over the curated spaces in
``hyperparameter_spaces.py``:
    - "grid_search": sklearn GridSearchCV (exhaustive over a discretized grid)
    - "random_search": sklearn RandomizedSearchCV (random sampling)
    - "bayesian_optimization": Optuna (sequential model-based search, with
      pruning-friendly TPE sampling)

All three share the same cross-validation strategy and the same curated
search space per model type, so results are comparable across methods.
"""

import logging
import threading
from contextlib import contextmanager
from typing import Any, Callable, Dict, Iterator, Optional

import numpy as np
import pandas as pd
from joblib import parallel_config
from sklearn.model_selection import (
    GridSearchCV,
    KFold,
    ParameterGrid,
    RandomizedSearchCV,
    StratifiedKFold,
    TimeSeriesSplit,
    cross_val_score,
)
from threadpoolctl import threadpool_limits

from app.core.config.settings import settings
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.modules.workflow.engine.nodes.ml import model_registry
from app.modules.workflow.engine.nodes.ml.hyperparameter_spaces import get_space

logger = logging.getLogger(__name__)

VALID_METHODS = ("none", "random_search", "grid_search", "bayesian_optimization")

# Safety caps so a curated 5-6 param space can't blow up into an
# impractically long exhaustive/randomized search.
_MAX_GRID_COMBINATIONS = 250
_MAX_RANDOM_ITER = 200
_DEFAULT_GRID_POINTS = 3
_DEFAULT_RANDOM_POINTS = 8
_DEFAULT_CV_FOLDS = 3
_DEFAULT_RANDOM_ITER = 20
_DEFAULT_BAYESIAN_TRIALS = 30

_SEARCH_LABELS = {
    "grid_search": "grid search",
    "random_search": "random search",
    "bayesian_optimization": "Bayesian optimization",
}


def _discretize(spec: Dict[str, Any], n_points: int) -> list:
    """Turn a continuous/int spec into a finite list of candidate values."""
    param_type = spec["type"]
    if param_type == "categorical":
        return list(spec["choices"])

    low, high = spec["low"], spec["high"]
    nullable = spec.get("nullable", False)

    if param_type == "int":
        n = max(2, min(n_points, high - low + 1))
        raw = np.linspace(low, high, n)
        values = sorted({int(round(v)) for v in raw})
    elif param_type == "float":
        n = max(2, n_points)
        raw = np.geomspace(max(low, 1e-12), high, n) if spec.get("log") else np.linspace(low, high, n)
        values = sorted({float(v) for v in raw})
    else:
        raise ValueError(f"Unknown hyperparameter spec type: {param_type}")

    return ([None] + values) if nullable else values


def _build_param_grid(tunable_space: Dict[str, Dict[str, Any]], points: int) -> Dict[str, list]:
    grid = {name: _discretize(spec, points) for name, spec in tunable_space.items()}
    total_combinations = 1
    for values in grid.values():
        total_combinations *= max(1, len(values))
    if total_combinations > _MAX_GRID_COMBINATIONS and points > 2:
        logger.warning(
            f"Grid search space has {total_combinations} combinations (> {_MAX_GRID_COMBINATIONS}); "
            f"reducing resolution to 2 points per parameter."
        )
        return _build_param_grid(tunable_space, points=2)
    return grid


def _optuna_suggest(trial, name: str, spec: Dict[str, Any]):
    param_type = spec["type"]
    if param_type == "categorical":
        return trial.suggest_categorical(name, spec["choices"])
    if spec.get("nullable"):
        return trial.suggest_categorical(name, _discretize(spec, 6))
    if param_type == "int":
        return trial.suggest_int(name, spec["low"], spec["high"])
    if param_type == "float":
        return trial.suggest_float(name, spec["low"], spec["high"], log=spec.get("log", False))
    raise ValueError(f"Unknown hyperparameter spec type: {param_type}")


def _build_cv(is_classification: bool, is_time_based: bool, y_train: pd.Series, cv_folds: int):
    """
    Pick a CV splitter appropriate for the split method and target.

    Time-based splits must keep using TimeSeriesSplit internally too — a
    shuffled KFold during the search would leak "future" rows into training
    for exactly the reason the time-based split exists in the first place.
    """
    if is_time_based:
        return TimeSeriesSplit(n_splits=cv_folds)

    if is_classification:
        min_class_count = int(y_train.value_counts().min())
        if min_class_count < 2:
            logger.warning(
                "A target class has fewer than 2 samples; falling back to plain KFold (no stratification)."
            )
            return KFold(n_splits=cv_folds, shuffle=True, random_state=42)
        effective_folds = min(cv_folds, min_class_count)
        if effective_folds < cv_folds:
            logger.warning(
                f"Smallest target class has only {min_class_count} samples; "
                f"reducing cv folds from {cv_folds} to {effective_folds}."
            )
        return StratifiedKFold(n_splits=effective_folds, shuffle=True, random_state=42)

    return KFold(n_splits=cv_folds, shuffle=True, random_state=42)


def _tunable_space(model_type: str, user_params: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """The curated space minus every parameter the user fixed in modelParameters."""
    return {name: spec for name, spec in get_space(model_type).items() if name not in user_params}


def _plan_from_space(
    tunable_space: Dict[str, Dict[str, Any]], method: str, opt_config: Dict[str, Any]
) -> Dict[str, int]:
    cv_folds = int(opt_config.get("cvFolds", _DEFAULT_CV_FOLDS))
    if method == "grid_search":
        grid = _build_param_grid(tunable_space, points=int(opt_config.get("gridPoints", _DEFAULT_GRID_POINTS)))
        candidates = len(ParameterGrid(grid))
    elif method == "random_search":
        grid = _build_param_grid(tunable_space, points=int(opt_config.get("randomPoints", _DEFAULT_RANDOM_POINTS)))
        # RandomizedSearchCV samples without replacement from a finite grid,
        # so it never evaluates more candidates than the grid holds.
        n_iter = min(int(opt_config.get("nIter", _DEFAULT_RANDOM_ITER)), _MAX_RANDOM_ITER)
        candidates = min(n_iter, len(ParameterGrid(grid)))
    else:
        candidates = int(opt_config.get("nTrials", _DEFAULT_BAYESIAN_TRIALS))
    return {"candidates": candidates, "cv_folds": cv_folds, "fits": candidates * cv_folds}


def plan_search(
    model_type: str,
    user_params: Optional[Dict[str, Any]],
    method: str,
    opt_config: Optional[Dict[str, Any]],
) -> Optional[Dict[str, int]]:
    """
    Work out how many model fits a hyperparameter search will run, without any data.

    Returns {"candidates", "cv_folds", "fits"}, or None when no search runs
    (method "none", an unknown method, or nothing left to tune). Folds can only
    shrink once the data is known (small classes), so this is an upper bound.
    """
    if method not in _SEARCH_LABELS:
        return None
    tunable_space = _tunable_space(model_type, user_params or {})
    if not tunable_space:
        return None
    return _plan_from_space(tunable_space, method, opt_config or {})


def _raise_if_too_large(plan: Dict[str, int], method: str) -> None:
    max_fits = settings.ML_HPO_MAX_FITS
    if plan["fits"] <= max_fits:
        return
    raise AppException(
        error_key=ErrorKey.ML_TRAINING_SEARCH_TOO_LARGE,
        status_code=400,
        error_detail=(
            f"This {_SEARCH_LABELS[method]} would train {plan['fits']:,} models "
            f"({plan['candidates']:,} parameter combinations x {plan['cv_folds']} folds), "
            f"more than the limit of {max_fits:,}. Use fewer folds, grid points, iterations or trials, "
            "or fix some parameters in Model Parameters."
        ),
    )


def check_search_size(
    model_type: str,
    user_params: Optional[Dict[str, Any]],
    method: str,
    opt_config: Optional[Dict[str, Any]],
) -> Optional[Dict[str, int]]:
    """Refuse a search larger than ML_HPO_MAX_FITS before it starts; return its plan."""
    plan = plan_search(model_type, user_params, method, opt_config)
    if plan is not None:
        _raise_if_too_large(plan, method)
    return plan


def training_cores() -> int:
    """CPU cores one training job may use (ML_TRAINING_MAX_CORES)."""
    return max(1, int(settings.ML_TRAINING_MAX_CORES))


_native_limit_lock = threading.Lock()
_native_limit_users = 0
_native_limiter = None


@contextmanager
def native_thread_limit() -> Iterator[None]:
    """Cap the process's native thread pools (BLAS, OpenMP) at training_cores().

    The limit is process-wide, so overlapping fits share one: the first fit
    to start sets it and the last one to finish restores the original
    values, instead of the first to finish lifting it under the others.
    """
    global _native_limit_users, _native_limiter
    with _native_limit_lock:
        if _native_limit_users == 0:
            _native_limiter = threadpool_limits(limits=training_cores())
        _native_limit_users += 1
    try:
        yield
    finally:
        with _native_limit_lock:
            _native_limit_users -= 1
            if _native_limit_users == 0 and _native_limiter is not None:
                _native_limiter.restore_original_limits()
                _native_limiter = None


@contextmanager
def _single_threaded_cv_workers() -> Iterator[None]:
    """Give each cross-validation worker process one native thread.

    joblib otherwise lets every loky worker use cpu_count // n_jobs BLAS and
    OpenMP threads, so n_jobs workers would still use every core.
    """
    with parallel_config(backend="loky", inner_max_num_threads=1):
        yield


def optimize_hyperparameters(
    model_type: str,
    is_classification: bool,
    X_train: pd.DataFrame,
    y_train: pd.Series,
    method: str,
    user_params: Dict[str, Any],
    opt_config: Optional[Dict[str, Any]],
    is_time_based: bool,
    on_trial: Optional[Callable[[int, int], None]] = None,
) -> Optional[Dict[str, Any]]:
    """
    Run hyperparameter optimization and return a fitted best estimator.

    The search uses at most ML_TRAINING_MAX_CORES cores: that many
    cross-validation workers, each fitting a single-threaded estimator.

    Args:
        user_params: The raw `modelParameters` the user configured on the
            node. Any key present here is treated as fixed and excluded from
            the search (least-surprise: an explicit value the user set is
            never silently overridden by the search).
        opt_config: Optional `{scoring, cvFolds, nIter, nTrials, timeoutSeconds,
            gridPoints}` overrides.
        on_trial: Optional callback(finished_trials, total_trials), called
            after each Bayesian optimization trial.

    Returns:
        None if this model type has no curated search space left to tune
        (e.g. linear_regression, or every tunable param was fixed by the
        user) — caller should fall back to plain training. Otherwise:
        {"model": <fitted estimator>, "best_params": {...tuned params...},
         "search_metadata": {...}}
    """
    opt_config = opt_config or {}
    tunable_space = _tunable_space(model_type, user_params)

    if not tunable_space:
        logger.info(f"No tunable hyperparameters left for '{model_type}' (space empty or fully fixed by user).")
        return None

    _raise_if_too_large(_plan_from_space(tunable_space, method, opt_config), method)

    defaults = model_registry.MODEL_DEFAULT_PARAMS.get(model_type, {})
    constant_params = {
        k: v for k, v in {**defaults, **user_params}.items() if k not in tunable_space
    }
    # Parallelism comes from the CV workers; threaded estimators inside them
    # would multiply the cores used, so each fit gets one thread.
    constant_params = model_registry.cap_estimator_threads(model_type, constant_params, 1)
    n_jobs = training_cores()

    cv_folds = int(opt_config.get("cvFolds", _DEFAULT_CV_FOLDS))
    cv = _build_cv(is_classification, is_time_based, y_train, cv_folds)
    scoring = opt_config.get("scoring") or ("accuracy" if is_classification else "r2")

    logger.info(
        f"Running {method} for '{model_type}' over params {list(tunable_space.keys())} "
        f"(scoring={scoring}, cv_folds={cv_folds})"
    )

    if method == "grid_search":
        param_grid = _build_param_grid(tunable_space, points=int(opt_config.get("gridPoints", _DEFAULT_GRID_POINTS)))
        estimator = model_registry.build_estimator(model_type, is_classification, constant_params)
        search = GridSearchCV(estimator, param_grid, cv=cv, scoring=scoring, refit=True, n_jobs=n_jobs, error_score="raise")
        with _single_threaded_cv_workers():
            search.fit(X_train, y_train)
        n_candidates = len(search.cv_results_["params"])
        return {
            "model": search.best_estimator_,
            "best_params": search.best_params_,
            "search_metadata": {
                "method": method,
                "scoring": scoring,
                "cv_folds": cv_folds,
                "best_score": float(search.best_score_),
                "candidates_evaluated": n_candidates,
                "search_space": list(tunable_space.keys()),
            },
        }

    if method == "random_search":
        param_distributions = _build_param_grid(
            tunable_space, points=int(opt_config.get("randomPoints", _DEFAULT_RANDOM_POINTS))
        )
        n_iter = min(int(opt_config.get("nIter", _DEFAULT_RANDOM_ITER)), _MAX_RANDOM_ITER)
        estimator = model_registry.build_estimator(model_type, is_classification, constant_params)
        search = RandomizedSearchCV(
            estimator,
            param_distributions,
            n_iter=n_iter,
            cv=cv,
            scoring=scoring,
            refit=True,
            n_jobs=n_jobs,
            random_state=42,
            error_score="raise",
        )
        with _single_threaded_cv_workers():
            search.fit(X_train, y_train)
        return {
            "model": search.best_estimator_,
            "best_params": search.best_params_,
            "search_metadata": {
                "method": method,
                "scoring": scoring,
                "cv_folds": cv_folds,
                "best_score": float(search.best_score_),
                "candidates_evaluated": n_iter,
                "search_space": list(tunable_space.keys()),
            },
        }

    if method == "bayesian_optimization":
        try:
            import optuna
        except ImportError as e:
            raise AppException(
                error_key=ErrorKey.INTERNAL_ERROR,
                error_detail="Optuna is not installed. Please install it with: pip install optuna",
            ) from e

        optuna.logging.set_verbosity(optuna.logging.WARNING)

        def objective(trial):
            trial_params = {name: _optuna_suggest(trial, name, spec) for name, spec in tunable_space.items()}
            estimator = model_registry.build_estimator(model_type, is_classification, {**constant_params, **trial_params})
            scores = cross_val_score(estimator, X_train, y_train, cv=cv, scoring=scoring, n_jobs=n_jobs)
            return float(scores.mean())

        n_trials = int(opt_config.get("nTrials", _DEFAULT_BAYESIAN_TRIALS))
        timeout = opt_config.get("timeoutSeconds")
        callbacks = []
        if on_trial is not None:
            callbacks.append(lambda study, _trial: on_trial(len(study.trials), n_trials))
        study = optuna.create_study(direction="maximize", sampler=optuna.samplers.TPESampler(seed=42))
        with _single_threaded_cv_workers():
            study.optimize(
                objective, n_trials=n_trials, timeout=timeout, show_progress_bar=False, callbacks=callbacks
            )

        best_params = study.best_params
        final_params = model_registry.cap_estimator_threads(
            model_type, {**constant_params, **best_params}, n_jobs
        )
        best_estimator = model_registry.build_estimator(model_type, is_classification, final_params)
        best_estimator.fit(X_train, y_train)

        return {
            "model": best_estimator,
            "best_params": best_params,
            "search_metadata": {
                "method": method,
                "scoring": scoring,
                "cv_folds": cv_folds,
                "best_score": float(study.best_value),
                "candidates_evaluated": len(study.trials),
                "search_space": list(tunable_space.keys()),
            },
        }

    raise AppException(
        error_key=ErrorKey.INTERNAL_ERROR,
        error_detail=f"Unsupported hyperparameter optimization method: {method}",
    )
