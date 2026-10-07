"""Dataset files: conversations of turns that an import adds to an existing dataset."""

import json
import math
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.schemas.eval_bundle import EVALUATION_BUNDLE_KIND, EVALUATION_BUNDLE_SET_KIND

DATASET_FILE_KIND = "genassist.dataset"
DATASET_FILE_SCHEMA_VERSION = 1

MAX_IMPORT_FILES = 20
MAX_IMPORT_FILE_BYTES = 5 * 1024 * 1024
MAX_IMPORT_TOTAL_BYTES = 10 * 1024 * 1024
# Same ceiling as the dataset of one evaluation bundle.
MAX_IMPORT_TURNS = 5000
# Problems listed for a rejected file; the rest are only counted.
MAX_FILE_ERRORS = 10

# Marks turns that came from a file, as "imported" marks a stored conversation.
FILE_IMPORT_TAG = "imported-file"
_RESERVED_TAGS = frozenset({"imported", FILE_IMPORT_TAG})

_BUNDLE_KINDS = frozenset({EVALUATION_BUNDLE_KIND, EVALUATION_BUNDLE_SET_KIND})
_TURN_FIELDS = frozenset({"input_data", "expected_output", "tags", "weight"})

FILE_STATUS_OK = "ok"
FILE_STATUS_FAILED = "failed"
FILE_STATUS_EVALUATION_BUNDLE = "evaluation_bundle"


@dataclass
class DatasetTurn:
    input_data: Dict[str, Any]
    expected_output: Optional[Dict[str, Any]]
    tags: List[str]
    weight: Optional[float]


@dataclass
class ParsedDatasetFile:
    status: str
    conversations: List[List[DatasetTurn]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


@dataclass
class DatasetUpload:
    filename: str
    content: bytes = b""
    # Set when the file was refused before parsing, e.g. for its size.
    error: Optional[str] = None


class _UnsupportedNumber(ValueError):
    pass


def invalid_file_import(detail: str) -> AppException:
    return AppException(
        status_code=400,
        error_key=ErrorKey.DATASET_FILE_IMPORT_INVALID,
        error_detail=detail,
    )


def turn_limit_error(turns: int) -> Optional[str]:
    if turns <= MAX_IMPORT_TURNS:
        return None
    return (
        f"These files add {turns:,} turns, and one import can add at most "
        f"{MAX_IMPORT_TURNS:,}. Import them in smaller batches."
    )


async def read_uploads(files: Sequence[Any]) -> List[DatasetUpload]:
    """Read uploaded files within the import limits; a refused file never stops the rest."""
    if len(files) > MAX_IMPORT_FILES:
        raise invalid_file_import(f"Choose at most {MAX_IMPORT_FILES} files at a time.")

    uploads: List[DatasetUpload] = []
    total = 0
    for file in files:
        name = _display_name(file.filename)
        if not name.lower().endswith(".json"):
            uploads.append(DatasetUpload(name, error="Only .json files can be imported."))
            continue
        content = await file.read(MAX_IMPORT_FILE_BYTES + 1)
        if len(content) > MAX_IMPORT_FILE_BYTES:
            uploads.append(
                DatasetUpload(
                    name,
                    error=f"The file is larger than {_megabytes(MAX_IMPORT_FILE_BYTES)} MB.",
                )
            )
            continue
        total += len(content)
        if total > MAX_IMPORT_TOTAL_BYTES:
            raise invalid_file_import(
                f"The files add up to more than {_megabytes(MAX_IMPORT_TOTAL_BYTES)} MB. "
                "Import them in smaller batches."
            )
        uploads.append(DatasetUpload(name, content=content))
    return uploads


def parse_dataset_file(raw: bytes) -> ParsedDatasetFile:
    """Read one dataset file; a file with any problem is rejected as a whole."""
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return _failed("The file is not UTF-8 text.")
    if not text.strip():
        return _failed("The file is empty.")
    try:
        data = json.loads(text, parse_constant=_reject_constant, parse_float=_finite_float)
    except json.JSONDecodeError as error:
        return _failed(
            f"The file is not valid JSON (line {error.lineno}, column {error.colno})."
        )
    except _UnsupportedNumber as error:
        return _failed(str(error))
    except (ValueError, RecursionError):
        return _failed("The file could not be read as JSON.")

    if not isinstance(data, dict):
        return _failed('The file must hold a JSON object with a "conversations" list.')
    kind = data.get("kind", DATASET_FILE_KIND)
    if isinstance(kind, str) and kind in _BUNDLE_KINDS:
        return ParsedDatasetFile(
            status=FILE_STATUS_EVALUATION_BUNDLE,
            errors=[
                "This is an evaluation bundle, not a dataset file. "
                "Import it on the Evaluations page."
            ],
        )
    if kind != DATASET_FILE_KIND:
        return _failed(
            f'The file is not a dataset file. Its "kind" must be "{DATASET_FILE_KIND}".'
        )
    version = data.get("schema_version", DATASET_FILE_SCHEMA_VERSION)
    if isinstance(version, bool) or not isinstance(version, int) or version < 1:
        return _failed('"schema_version" must be a whole number, such as 1.')
    if version > DATASET_FILE_SCHEMA_VERSION:
        return _failed(
            "The file was made by a newer version of GenAssist and cannot be imported here."
        )
    conversations = data.get("conversations")
    if not isinstance(conversations, list):
        return _failed('The file has no "conversations" list.')
    if not conversations:
        return _failed("The file has no conversations.")

    errors: List[str] = []
    parsed = [
        _parse_conversation(conversation, number, errors)
        for number, conversation in enumerate(conversations, 1)
    ]
    if errors:
        return ParsedDatasetFile(status=FILE_STATUS_FAILED, errors=_capped(errors))
    return ParsedDatasetFile(status=FILE_STATUS_OK, conversations=parsed)


def conversation_key(
    turns: Iterable[Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]],
) -> str:
    """A conversation's identity by content, so a repeated import can be recognized."""
    return json.dumps(
        [[input_data or {}, expected or None] for input_data, expected in turns],
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _parse_conversation(raw: Any, number: int, errors: List[str]) -> List[DatasetTurn]:
    where = f"Conversation {number}"
    if not isinstance(raw, dict):
        errors.append(f"{where} is not an object.")
        return []
    turns = raw.get("turns")
    if not isinstance(turns, list):
        errors.append(f'{where} has no "turns" list.')
        return []
    if not turns:
        errors.append(f"{where} has no turns.")
        return []
    # A turn joins the conversation's memory only through its message.
    needs_message = len(turns) > 1
    parsed = []
    for turn_number, raw_turn in enumerate(turns, 1):
        turn = _parse_turn(raw_turn, f"{where}, turn {turn_number}", needs_message, errors)
        if turn:
            parsed.append(turn)
    return parsed


def _parse_turn(
    raw: Any, where: str, needs_message: bool, errors: List[str]
) -> Optional[DatasetTurn]:
    if not isinstance(raw, dict):
        errors.append(f"{where} is not an object.")
        return None

    problems: List[str] = []
    unknown = sorted(key for key in raw if key not in _TURN_FIELDS)
    if unknown:
        names = ", ".join(f'"{key}"' for key in unknown)
        problems.append(f"unknown field{'s' if len(unknown) > 1 else ''} {names}")
    input_data = raw.get("input_data")
    if not isinstance(input_data, dict) or not input_data:
        problems.append('"input_data" must be an object with at least one field')
    elif "message" in input_data and not isinstance(input_data["message"], str):
        problems.append('"message" must be text')
    elif needs_message and "message" not in input_data:
        problems.append(
            '"input_data" needs a "message", as every turn of a multi-turn conversation does'
        )
    expected = raw.get("expected_output")
    if expected is not None and not isinstance(expected, dict):
        problems.append('"expected_output" must be an object, such as {"value": "..."}')
    tags = raw.get("tags")
    if tags is not None and not (
        isinstance(tags, list) and all(isinstance(tag, str) for tag in tags)
    ):
        problems.append('"tags" must be a list of text values')
    weight = raw.get("weight")
    if weight is not None and _as_number(weight) is None:
        problems.append('"weight" must be a number')
    if problems:
        errors.append(f"{where}: {'; '.join(problems)}.")
        return None

    return DatasetTurn(
        input_data=input_data,
        expected_output=expected or None,
        tags=_with_import_tag(tags or []),
        weight=_as_number(weight),
    )


def _with_import_tag(tags: List[str]) -> List[str]:
    kept = [tag.strip() for tag in tags if tag.strip() and tag.strip() not in _RESERVED_TAGS]
    return list(dict.fromkeys([*kept, FILE_IMPORT_TAG]))


def _as_number(value: Any) -> Optional[float]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        number = float(value)
    except OverflowError:
        return None
    return number if math.isfinite(number) else None


def _reject_constant(name: str) -> Any:
    raise _UnsupportedNumber(f"The file contains {name}, which JSON does not allow.")


def _finite_float(literal: str) -> float:
    value = float(literal)
    if not math.isfinite(value):
        raise _UnsupportedNumber(f"The number {literal[:20]} is too large.")
    return value


def _capped(errors: List[str]) -> List[str]:
    if len(errors) <= MAX_FILE_ERRORS:
        return errors
    hidden = len(errors) - MAX_FILE_ERRORS
    return [
        *errors[:MAX_FILE_ERRORS],
        f"{hidden} more problem{'s' if hidden > 1 else ''} not listed.",
    ]


def _failed(error: str) -> ParsedDatasetFile:
    return ParsedDatasetFile(status=FILE_STATUS_FAILED, errors=[error])


def _display_name(filename: Optional[str]) -> str:
    return (filename or "").replace("\\", "/").rsplit("/", 1)[-1] or "Untitled file"


def _megabytes(size: int) -> int:
    return size // (1024 * 1024)
