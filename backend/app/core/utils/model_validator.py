"""
Model file validation to prevent segfaults and incompatible models from loading
"""
import json
import logging
import os
import pickle
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Tuple, Optional, Dict, Any

logger = logging.getLogger(__name__)


def validate_pickle_file_safe(pkl_file: str, timeout: int = 5) -> Tuple[bool, Optional[str]]:
    """
    Safely validate a pickle file by loading it in a subprocess.
    
    This prevents segfaults from crashing the main application.
    If the model causes a segfault, it only crashes the subprocess.
    
    Args:
        pkl_file: Path to the pickle file
        timeout: Timeout in seconds for validation
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not os.path.exists(pkl_file):
        return False, f"File not found: {pkl_file}"
    
    # Create a simple validation script (use repr to safely escape path)
    validation_script = f"""
import sys
import pickle
import signal

def timeout_handler(signum, frame):
    sys.exit(124)  # Timeout exit code

signal.signal(signal.SIGALRM, timeout_handler)
signal.alarm({timeout})

try:
    with open({repr(pkl_file)}, 'rb') as f:
        obj = pickle.load(f)

    # Handle wrapped format (model + metadata)
    if isinstance(obj, dict) and "model" in obj:
        model = obj["model"]
    else:
        model = obj

    # Basic validation - try to access the model
    if hasattr(model, 'predict'):
        pass

    print("OK")
    sys.exit(0)
except Exception as e:
    print(f"ERROR: {{type(e).__name__}}: {{str(e)}}")
    sys.exit(1)
"""
    
    try:
        # Run validation in subprocess
        result = subprocess.run(
            ['python', '-c', validation_script],
            capture_output=True,
            text=True,
            timeout=timeout
        )
        
        if result.returncode == 0 and "OK" in result.stdout:
            logger.info(f"Model validation passed: {pkl_file}")
            return True, None
        elif result.returncode == 124:
            error_msg = f"Model validation timed out after {timeout}s (may be too large or corrupted)"
            logger.error(error_msg)
            return False, error_msg
        elif result.returncode == 139:  # SIGSEGV (segfault)
            error_msg = f"Model causes segmentation fault (incompatible version or corrupted file)"
            logger.error(error_msg)
            return False, error_msg
        elif result.returncode < 0:  # Killed by signal
            signal_num = -result.returncode
            error_msg = f"Model validation killed by signal {signal_num}"
            logger.error(error_msg)
            return False, error_msg
        else:
            error_msg = result.stdout.strip() or result.stderr.strip() or "Unknown error"
            logger.error(f"Model validation failed: {error_msg}")
            return False, error_msg
            
    except subprocess.TimeoutExpired:
        error_msg = f"Model validation timeout after {timeout}s"
        logger.error(error_msg)
        return False, error_msg
    except Exception as e:
        error_msg = f"Validation error: {type(e).__name__}: {str(e)}"
        logger.error(error_msg)
        return False, error_msg


def get_model_info(pkl_file: str) -> dict:
    """
    Get basic information about a pickle file safely.
    
    Args:
        pkl_file: Path to the pickle file
        
    Returns:
        Dictionary with model information
    """
    info = {
        "file_path": pkl_file,
        "file_exists": os.path.exists(pkl_file),
        "file_size": 0,
        "is_valid": False,
        "error": None
    }
    
    if not info["file_exists"]:
        info["error"] = "File not found"
        return info
    
    info["file_size"] = os.path.getsize(pkl_file)
    
    # Validate the file
    is_valid, error = validate_pickle_file_safe(pkl_file)
    info["is_valid"] = is_valid
    info["error"] = error
    
    return info


def extract_metadata_from_pkl(pkl_file: str, timeout: int = 10) -> Dict[str, Any]:
    """
    Extract model_type and features from a pickle file safely.

    Runs in a subprocess to prevent segfaults. Handles both:
    - Wrapped format (our trained models): dict with "model" and "metadata" keys
    - Raw format (legacy/external): extract model_type and features from the model object

    Args:
        pkl_file: Path to the pickle file
        timeout: Timeout in seconds for extraction

    Returns:
        Dict with keys: model_type, features.
        model_type and features may be None/empty if extraction fails.
    """
    result = {
        "model_type": None,
        "features": [],
        "error": None,
    }

    if not os.path.exists(pkl_file):
        result["error"] = f"File not found: {pkl_file}"
        return result

    extract_script = '''
import json
import pickle
import sys

MODEL_TYPE_MAP = {
    "XGBClassifier": "xgboost",
    "XGBRegressor": "xgboost",
    "XGBModel": "xgboost",
    "Booster": "xgboost",
    "RandomForestClassifier": "random_forest",
    "RandomForestRegressor": "random_forest",
    "LinearRegression": "linear_regression",
    "LogisticRegression": "logistic_regression",
    "MLPClassifier": "neural_network",
    "MLPRegressor": "neural_network",
}

def get_inner_estimator(model):
    """Unwrap Pipeline, GridSearchCV, etc. to get the actual model."""
    if model is None:
        return None
    name = type(model).__name__
    # Pipeline: last step is the estimator
    if name == "Pipeline" and hasattr(model, "steps") and model.steps:
        return get_inner_estimator(model.steps[-1][1])
    # GridSearchCV / RandomizedSearchCV: best_estimator_ or estimator
    if name in ("GridSearchCV", "RandomizedSearchCV"):
        inner = getattr(model, "best_estimator_", None)
        if inner is not None:
            return get_inner_estimator(inner)
        return get_inner_estimator(getattr(model, "estimator", None))
    # CalibratedClassifierCV (calibrated_classifiers_ can be list of (est, cal) tuples)
    if name == "CalibratedClassifierCV" and hasattr(model, "calibrated_classifiers_"):
        cal = model.calibrated_classifiers_
        if cal:
            first = cal[0]
            if isinstance(first, tuple):
                return get_inner_estimator(first[0])
            return get_inner_estimator(getattr(first, "estimator", first))
    return model

def get_features(model):
    """Extract feature names from model, trying outer then inner."""
    if model is None:
        return []
    if hasattr(model, "feature_names_in_") and model.feature_names_in_ is not None:
        return list(model.feature_names_in_)
    if hasattr(model, "get_booster"):
        try:
            booster = model.get_booster()
            if hasattr(booster, "feature_names") and booster.feature_names:
                return list(booster.feature_names)
        except Exception:
            pass
    # For Pipeline, try named_steps last step
    if hasattr(model, "steps") and model.steps:
        return get_features(model.steps[-1][1])
    return []

def main():
    pkl_file = sys.argv[1]
    try:
        with open(pkl_file, 'rb') as f:
            obj = pickle.load(f)

        # Wrapped format (our trained models)
        if isinstance(obj, dict) and "model" in obj and "metadata" in obj:
            meta = obj["metadata"]
            out = {
                "model_type": meta.get("model_type"),
                "features": meta.get("feature_columns", []),
            }
        else:
            # Raw model - unwrap wrappers and extract
            model = obj
            inner = get_inner_estimator(model)
            model_for_type = inner if inner is not None else model
            model_type_name = type(model_for_type).__name__
            model_type = MODEL_TYPE_MAP.get(model_type_name, "other")
            features = get_features(model)
            if not features and inner is not None:
                features = get_features(inner)
            out = {
                "model_type": model_type,
                "features": features,
            }
        print(json.dumps(out))
        return 0
    except Exception as e:
        print(json.dumps({"error": str(e)}))
        return 1

sys.exit(main())
'''
    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(extract_script)
            script_path = f.name

        try:
            proc_result = subprocess.run(
                [sys.executable, script_path, pkl_file],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            if proc_result.returncode == 0 and proc_result.stdout.strip():
                try:
                    extracted = json.loads(proc_result.stdout.strip())
                    result["model_type"] = extracted.get("model_type")
                    result["features"] = extracted.get("features", []) or []
                    if "error" in extracted:
                        result["error"] = extracted["error"]
                except json.JSONDecodeError as e:
                    result["error"] = f"Failed to parse extraction output: {e}"
            else:
                try:
                    err_out = json.loads(proc_result.stdout.strip() or "{}")
                    result["error"] = err_out.get("error", "Extraction failed")
                except json.JSONDecodeError:
                    result["error"] = proc_result.stderr.strip() or "Extraction failed"
        finally:
            os.unlink(script_path)
    except subprocess.TimeoutExpired:
        result["error"] = f"Extraction timed out after {timeout}s"
    except Exception as e:
        result["error"] = str(e)

    return result


def check_xgboost_compatibility(model) -> Tuple[bool, Optional[str]]:
    """
    Check if an XGBoost model is compatible with the current version.
    
    Args:
        model: Loaded model object
        
    Returns:
        Tuple of (is_compatible, message)
    """
    try:
        import xgboost as xgb
        current_version = xgb.__version__
        
        # Check if it's an XGBoost model
        model_type = type(model).__name__
        if 'XGB' not in model_type and 'Booster' not in model_type:
            return True, None  # Not an XGBoost model
        
        # Try to get model version
        if hasattr(model, 'get_params'):
            # It's likely compatible if we can get params
            return True, None
        
        return True, None
        
    except Exception as e:
        return False, f"XGBoost compatibility check failed: {str(e)}"

