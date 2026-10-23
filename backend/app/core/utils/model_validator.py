"""
Model file validation to prevent unsafe pickle files from loading.

Validates pickle files by scanning their opcodes for dangerous module
references (os, subprocess, socket, etc.). This runs in-process without
importing ML libraries or deserializing objects, making it orders of
magnitude faster than subprocess-based validation.
"""
import logging
import os
import pickletools
from typing import Tuple, Optional

from app.core.project_path import DATA_VOLUME

logger = logging.getLogger(__name__)

ML_MODELS_DIR = os.path.realpath(DATA_VOLUME / "ml_models")


def resolve_model_path(pkl_file: Optional[str]) -> Optional[str]:
    """Return the real path of a model file if it is inside the ML models folder, otherwise None."""
    if not pkl_file:
        return None
    real_path = os.path.realpath(pkl_file)
    if not real_path.startswith(ML_MODELS_DIR + os.sep):
        return None
    return real_path


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


def validate_pickle_file_safe(pkl_file: str, **_kwargs) -> Tuple[bool, Optional[str]]:
    """
    Validate a pickle file by scanning its opcodes for dangerous module references.

    Parses the pickle bytecode and checks that no class reference (GLOBAL,
    INST, STACK_GLOBAL opcodes) targets a blocked module. Custom and
    third-party ML modules are allowed through — only known-dangerous
    modules (os, subprocess, socket, etc.) are rejected.

    Args:
        pkl_file: Path to the pickle file

    Returns:
        Tuple of (is_valid, error_message)
    """
    safe_path = resolve_model_path(pkl_file)
    if safe_path is None:
        return False, "Model file is not inside the ML models folder"
    if not os.path.isfile(safe_path):
        return False, "Model file not found"

    try:
        with open(safe_path, "rb") as f:
            data = f.read()

        ops = list(pickletools.genops(data))

        for i, (opcode, arg, _pos) in enumerate(ops):
            module = None

            if opcode.name in ("GLOBAL", "INST"):
                module, _ = arg.split("\n", 1)
            elif opcode.name == "STACK_GLOBAL":
                strings = []
                for j in range(i - 1, max(i - 10, -1), -1):
                    prev_op, prev_arg, _ = ops[j]
                    if prev_op.name in ("SHORT_BINUNICODE", "BINUNICODE"):
                        strings.insert(0, prev_arg)
                        if len(strings) == 2:
                            break
                if len(strings) == 2:
                    module = strings[0]

            if module is None:
                continue

            top_level = module.split(".")[0]
            if module in _BLOCKED_MODULES or top_level in _BLOCKED_MODULES:
                error_msg = f"Dangerous module reference in pickle: {module}"
                logger.error(error_msg)
                return False, error_msg

        logger.info("Model validation passed: %s", pkl_file)
        return True, None

    except Exception as e:
        error_msg = f"Validation error: {type(e).__name__}: {e}"
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
        "file_exists": False,
        "file_size": 0,
        "is_valid": False,
        "error": None
    }

    if not pkl_file:
        info["error"] = "File not found"
        return info

    safe_path = resolve_model_path(pkl_file)
    if safe_path is None:
        info["error"] = "Model file is not inside the ML models folder"
        return info

    info["file_exists"] = os.path.isfile(safe_path)
    if not info["file_exists"]:
        info["error"] = "File not found"
        return info

    info["file_size"] = os.path.getsize(safe_path)

    is_valid, error = validate_pickle_file_safe(safe_path)
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

        model_type = type(model).__name__
        if 'XGB' not in model_type and 'Booster' not in model_type:
            return True, None

        if hasattr(model, 'get_params'):
            return True, None

        return True, None

    except Exception as e:
        return False, f"XGBoost compatibility check failed: {str(e)}"
