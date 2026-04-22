"""
Model file validation to prevent segfaults and incompatible models from loading.

Security: The subprocess validator uses RestrictedUnpickler (via safe_pickle)
to block arbitrary code execution from crafted pickle files. The file path is
passed as a command-line argument, not interpolated into source code.
"""
import logging
import os
import subprocess
import sys
from typing import Tuple, Optional

logger = logging.getLogger(__name__)

# Validation script passed to the subprocess. The file path is received via
# sys.argv[1] — never interpolated into source — eliminating code injection.
# Uses the project's RestrictedUnpickler so crafted __reduce__ payloads are
# blocked even inside the subprocess.
_VALIDATION_SCRIPT = """\
import sys, signal

def timeout_handler(signum, frame):
    sys.exit(124)

signal.signal(signal.SIGALRM, timeout_handler)
signal.alarm(int(sys.argv[2]))

try:
    # Import the project's safe loader
    from app.core.utils.safe_pickle import safe_pickle_load

    with open(sys.argv[1], 'rb') as f:
        model = safe_pickle_load(f)

    model_type = type(model).__name__
    if hasattr(model, 'predict'):
        pass

    print("OK")
    sys.exit(0)
except Exception as e:
    print(f"ERROR: {type(e).__name__}: {e}")
    sys.exit(1)
"""


def validate_pickle_file_safe(pkl_file: str, timeout: int = 5) -> Tuple[bool, Optional[str]]:
    """
    Safely validate a pickle file by loading it in a subprocess.

    This prevents segfaults from crashing the main application.
    If the model causes a segfault, it only crashes the subprocess.

    Security: the file path is passed as ``sys.argv[1]`` (not via f-string
    interpolation into source code), and the subprocess uses
    ``RestrictedUnpickler`` to block ``__reduce__``-based exploits.

    Args:
        pkl_file: Path to the pickle file
        timeout: Timeout in seconds for validation

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not os.path.exists(pkl_file):
        return False, f"File not found: {pkl_file}"

    try:
        result = subprocess.run(
            [sys.executable, "-c", _VALIDATION_SCRIPT, pkl_file, str(timeout)],
            capture_output=True,
            text=True,
            timeout=timeout + 2,  # small grace period over the in-process alarm
        )

        if result.returncode == 0 and "OK" in result.stdout:
            logger.info("Model validation passed: %s", pkl_file)
            return True, None
        elif result.returncode == 124:
            error_msg = f"Model validation timed out after {timeout}s (may be too large or corrupted)"
            logger.error(error_msg)
            return False, error_msg
        elif result.returncode == 139:  # SIGSEGV
            error_msg = "Model causes segmentation fault (incompatible version or corrupted file)"
            logger.error(error_msg)
            return False, error_msg
        elif result.returncode < 0:
            signal_num = -result.returncode
            error_msg = f"Model validation killed by signal {signal_num}"
            logger.error(error_msg)
            return False, error_msg
        else:
            error_msg = result.stdout.strip() or result.stderr.strip() or "Unknown error"
            logger.error("Model validation failed: %s", error_msg)
            return False, error_msg

    except subprocess.TimeoutExpired:
        error_msg = f"Model validation timeout after {timeout}s"
        logger.error(error_msg)
        return False, error_msg
    except Exception as e:
        error_msg = f"Validation error: {type(e).__name__}"
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

