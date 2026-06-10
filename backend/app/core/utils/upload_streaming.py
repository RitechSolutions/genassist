"""Helpers for streaming large uploads without loading entire files into memory."""

from __future__ import annotations

import asyncio
import os
from typing import Optional, Tuple

from fastapi import UploadFile

DEFAULT_CHUNK_SIZE = 1024 * 1024  # 1 MiB


async def async_stream_uploadfile_to_path(
    upload_file: UploadFile,
    dest_path: str,
    max_bytes: Optional[int],
    chunk_size: int = DEFAULT_CHUNK_SIZE,
) -> Tuple[int, Optional[str]]:
    """
    Stream an UploadFile to a filesystem path.

    Returns (total_bytes_written, content_type).
    """
    parent = os.path.dirname(os.path.abspath(dest_path))
    if parent:
        os.makedirs(parent, exist_ok=True)

    total = 0
    mime = upload_file.content_type

    def _write_chunk(f, data: bytes) -> None:
        f.write(data)

    with open(dest_path, "wb") as out:
        while True:
            chunk = await upload_file.read(chunk_size)
            if not chunk:
                break
            total += len(chunk)
            if max_bytes is not None and total > max_bytes:
                raise ValueError(
                    f"File exceeds maximum allowed size ({max_bytes} bytes)."
                )
            await asyncio.to_thread(_write_chunk, out, chunk)

    return total, mime


async def append_bytes_to_path(path: str, data: bytes) -> None:
    """Append bytes to a file (used for chunked uploads)."""

    def _append() -> None:
        parent = os.path.dirname(os.path.abspath(path))
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(path, "ab") as f:
            f.write(data)

    await asyncio.to_thread(_append)
