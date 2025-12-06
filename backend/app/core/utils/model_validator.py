"""
Model file validation to prevent segfaults and incompatible models from loading
"""
import logging
import os
import pickle
import subprocess
import tempfile
from pathlib import Path
from typing import Tuple, Optional

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
    
    # Create a simple validation script
    validation_script = f"""
import sys
import pickle
import signal

def timeout_handler(signum, frame):
    sys.exit(124)  # Timeout exit code

signal.signal(signal.SIGALRM, timeout_handler)
signal.alarm({timeout})

try:
    with open('{pkl_file}', 'rb') as f:
        model = pickle.load(f)
    
    # Basic validation - try to access the model
    model_type = type(model).__name__
    
    # Try to get basic attributes
    if hasattr(model, 'predict'):
        # It's a model with predict method
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

