"""Upload limit for Train Data Source files.

Training data uploads may be much larger than other File Manager uploads, so
they are marked with ``purpose="training_data"`` on every upload path (single
multipart POST, chunked session, direct S3 presigned PUT) and checked against
their own ceiling here. Every other upload keeps the regular File Manager limit.
"""

from pathlib import Path
from typing import Literal, Optional

from app.core.config.settings import settings
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException

TRAINING_DATA_PURPOSE = "training_data"
UploadPurpose = Literal["training_data"]


def is_training_upload(purpose: Optional[str]) -> bool:
    return purpose == TRAINING_DATA_PURPOSE


def training_upload_max_bytes() -> int:
    """The effective maximum size of one training data upload.

    Never above ML_EXTRACT_MAX_BYTES: a file Train Data Source would refuse to
    extract is refused at upload time instead.
    """
    return min(settings.ML_TRAINING_UPLOAD_MAX_BYTES, settings.ML_EXTRACT_MAX_BYTES)


def format_bytes(size: int) -> str:
    """Human-readable size in binary units (2147483648 -> "2 GB")."""
    value = float(size)
    for unit in ("bytes", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            break
        value /= 1024
    if unit == "bytes":
        return f"{int(value)} bytes"
    return f"{value:.1f}".rstrip("0").rstrip(".") + f" {unit}"


def training_upload_too_large(size: Optional[int], max_bytes: int) -> AppException:
    if size is None:
        detail = (
            "This file is larger than the maximum training data upload size "
            f"of {format_bytes(max_bytes)}."
        )
    else:
        detail = (
            f"This file is {format_bytes(size)}, which is larger than the maximum "
            f"training data upload size of {format_bytes(max_bytes)}."
        )
    return AppException(ErrorKey.ML_TRAINING_UPLOAD_TOO_LARGE, 413, detail)


def check_training_upload_size(size: Optional[int]) -> None:
    """Raise a clear 413 when a declared or received size is over the limit."""
    max_bytes = training_upload_max_bytes()
    if size is not None and size > max_bytes:
        raise training_upload_too_large(size, max_bytes)


def check_training_upload_name(filename: Optional[str]) -> None:
    """Only training file types may use the larger training upload limit."""
    # Imported here: the readers pull in pandas/pyarrow, which the File
    # Manager routes otherwise don't need.
    from app.modules.workflow.engine.nodes.ml.training_file_readers import (
        ensure_supported_training_file,
    )

    ensure_supported_training_file(Path(filename or ""))
