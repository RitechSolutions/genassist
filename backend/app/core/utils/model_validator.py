"""Static validation for uploaded pickle model files."""

import codecs
import io
import logging
import os
import pickle
import pickletools
from typing import Any, Optional, Tuple

from app.core.utils.safe_pickle import is_pickle_global_allowed

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


_UNKNOWN_STACK_VALUE = object()
_GLOBAL_CLASS_VALUE = object()
_DIRECT_GLOBAL_OPCODES = frozenset({"GLOBAL", "INST"})
_MEMO_STORE_OPCODES = frozenset({"PUT", "BINPUT", "LONG_BINPUT", "MEMOIZE"})
_MEMO_LOAD_OPCODES = frozenset({"GET", "BINGET", "LONG_BINGET"})
_STRING_OPCODES = frozenset(
    {
        "STRING",
        "BINSTRING",
        "SHORT_BINSTRING",
        "UNICODE",
        "BINUNICODE",
        "SHORT_BINUNICODE",
        "BINUNICODE8",
    }
)
_UNSUPPORTED_OPCODES = frozenset({"EXT1", "EXT2", "EXT4", "PERSID", "BINPERSID", "NEXT_BUFFER", "READONLY_BUFFER"})


class _PickleValidationError(ValueError):
    """A safe, user-facing pickle validation failure."""


def _malformed_pickle_error(position: int) -> _PickleValidationError:
    return _PickleValidationError(
        f"Malformed pickle file near byte offset {position}. Re-export the model with a supported pickle format."
    )


def _parse_direct_global(arg: Any, position: int) -> tuple[str, str]:
    if not isinstance(arg, str):
        raise _malformed_pickle_error(position)

    module, separator, name = arg.partition(" ")
    if arg.count(" ") != 1 or not separator or not module or not name:
        raise _malformed_pickle_error(position)

    return module, name


def _validate_global_reference(module: str, name: str, opcode_name: str, position: int) -> None:
    if is_pickle_global_allowed(module, name):
        return

    reference = f"{module}.{name}"
    raise _PickleValidationError(
        f"Disallowed pickle global {reference!a} in {opcode_name} at byte offset {position}. "
        "Only supported ML framework classes are permitted."
    )


def _find_topmost_mark(stack: list[Any], position: int) -> int:
    for index in range(len(stack) - 1, -1, -1):
        if stack[index] is pickletools.markobject:
            return index
    raise _malformed_pickle_error(position)


def _read_direct_global(stream: io.BytesIO) -> str:
    module = pickletools.read_stringnl(stream, decode=False, stripquotes=False)
    name = pickletools.read_stringnl(stream, decode=False, stripquotes=False)
    return f"{module.decode('utf-8')} {name.decode('utf-8')}"


def _generate_pickle_ops(data: bytes):
    """Generate pickle operations while decoding Python 2 strings as latin-1."""
    stream = io.BytesIO(data)

    while True:
        position = stream.tell()
        code = stream.read(1)
        opcode = pickletools.code2op.get(code.decode("latin-1"))
        if opcode is None:
            if not code:
                raise ValueError("pickle exhausted before seeing STOP")
            raise ValueError(f"unknown pickle opcode at byte offset {position}")

        if opcode.arg is None:
            arg = None
        elif opcode.name in _DIRECT_GLOBAL_OPCODES:
            arg = _read_direct_global(stream)
        elif opcode.name == "STRING":
            encoded = pickletools.read_stringnl(stream, decode=False)
            arg = codecs.escape_decode(encoded)[0].decode("latin-1")
        else:
            arg = opcode.arg.reader(stream)

        yield opcode, arg, position
        if opcode.name == "STOP":
            return


def _validate_pickle_data(data: bytes) -> None:
    stack: list[Any] = []
    memo: dict[int, Any] = {}

    for opcode, arg, position in _generate_pickle_ops(data):
        opcode_name = opcode.name

        if opcode_name == "PROTO" and (not isinstance(arg, int) or arg > pickle.HIGHEST_PROTOCOL):
            raise _PickleValidationError(
                f"Unsupported pickle protocol at byte offset {position}. "
                "Re-export the model with the current Python version."
            )
        if opcode_name == "FRAME" and (not isinstance(arg, int) or position + 9 + arg > len(data)):
            raise _malformed_pickle_error(position)
        if opcode_name in _DIRECT_GLOBAL_OPCODES:
            module, name = _parse_direct_global(arg, position)
            _validate_global_reference(module, name, opcode_name, position)
        elif opcode_name == "STACK_GLOBAL":
            if len(stack) < 2 or not isinstance(stack[-2], str) or not isinstance(stack[-1], str):
                raise _PickleValidationError(
                    f"Unable to safely resolve STACK_GLOBAL at byte offset {position}. "
                    "Re-export the model with a supported pickle format."
                )
            _validate_global_reference(stack[-2], stack[-1], opcode_name, position)
        elif opcode_name == "BUILD" and len(stack) >= 2 and stack[-2] is _GLOBAL_CLASS_VALUE:
            raise _PickleValidationError(
                f"Unsafe pickle BUILD targets a class object at byte offset {position}. "
                "Re-export the model with a supported pickle format."
            )
        elif opcode_name in _UNSUPPORTED_OPCODES:
            raise _PickleValidationError(
                f"Unsupported pickle opcode {opcode_name} at byte offset {position}. "
                "Re-export the model without external pickle references."
            )

        before = opcode.stack_before
        after = opcode.stack_after
        values_to_pop = len(before)

        if pickletools.markobject in before or (opcode_name == "POP" and stack and stack[-1] is pickletools.markobject):
            mark_index = _find_topmost_mark(stack, position)
            del stack[mark_index:]
            values_to_pop = before.index(pickletools.markobject) if pickletools.markobject in before else 0

        if opcode_name in _MEMO_STORE_OPCODES:
            memo_index = len(memo) if opcode_name == "MEMOIZE" else arg
            if not isinstance(memo_index, int) or not stack:
                raise _malformed_pickle_error(position)
            if stack[-1] is pickletools.markobject:
                raise _malformed_pickle_error(position)
            memo[memo_index] = stack[-1]

        if opcode_name in _MEMO_LOAD_OPCODES:
            if not isinstance(arg, int) or arg not in memo:
                raise _malformed_pickle_error(position)
            values_to_push = [memo[arg]]
        elif opcode_name in {"GLOBAL", "STACK_GLOBAL"}:
            values_to_push = [_GLOBAL_CLASS_VALUE]
        elif opcode_name == "MEMOIZE":
            values_to_push = [stack[-1]]
        elif opcode_name == "DUP":
            if not stack:
                raise _malformed_pickle_error(position)
            values_to_push = [stack[-1], stack[-1]]
        elif opcode_name in _STRING_OPCODES and len(after) == 1:
            values_to_push = [arg]
        else:
            values_to_push = [
                pickletools.markobject if value is pickletools.markobject else _UNKNOWN_STACK_VALUE for value in after
            ]

        if len(stack) < values_to_pop:
            raise _malformed_pickle_error(position)
        if values_to_pop:
            del stack[-values_to_pop:]
        stack.extend(values_to_push)

    if stack:
        raise _malformed_pickle_error(len(data))


def validate_pickle_file_safe(pkl_file: str, **_kwargs) -> Tuple[bool, Optional[str]]:
    """
    Validate a pickle without importing modules or deserializing objects.

    The symbolic opcode scan resolves GLOBAL, INST, and STACK_GLOBAL
    references and applies the same allowlist used by RestrictedUnpickler.
    Malformed streams and references that cannot be resolved statically are
    rejected rather than treated as safe.

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
    except OSError as exc:
        error_msg = f"Unable to read pickle file ({type(exc).__name__})."
        logger.error("Unable to read pickle file %s: %s", pkl_file, type(exc).__name__)
        return False, error_msg

    try:
        _validate_pickle_data(data)

        logger.info("Model validation passed: %s", pkl_file)
        return True, None

    except _PickleValidationError as exc:
        error_msg = str(exc)
        logger.error(error_msg)
        return False, error_msg
    except Exception as exc:
        error_msg = "Malformed pickle file. Re-export the model with a supported pickle format."
        logger.error("Pickle parsing failed for %s: %s", pkl_file, type(exc).__name__)
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
        "error": None,
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
        if "XGB" not in model_type and "Booster" not in model_type:
            return True, None

        if hasattr(model, "get_params"):
            return True, None

        return True, None

    except Exception as e:
        return False, f"XGBoost compatibility check failed: {str(e)}"
