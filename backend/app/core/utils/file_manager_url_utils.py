"""Detect File Manager API URLs embedded in text (GDPR / erasure helpers).

Durable references appear as ``.../file-manager/files/<uuid>/source`` (optional
query string). Used to purge object storage when conversations are removed.
"""

from __future__ import annotations

import json
import re
from typing import Any, Optional, Sequence
from uuid import UUID

# Path segment after /files/ up to next /, ?, or end (UUID + optional subpath)
_FILE_MANAGER_PATH_UUID_RE = re.compile(
    r"/files/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})(?:/|\?|$)",
    re.IGNORECASE,
)


def extract_file_manager_uuids_from_text(text: str | None) -> set[UUID]:
    """Return all UUIDs that appear in File Manager ``/files/<uuid>/`` URLs."""
    if not text:
        return set()
    out: set[UUID] = set()
    for m in _FILE_MANAGER_PATH_UUID_RE.finditer(text):
        try:
            out.add(UUID(m.group(1)))
        except ValueError:
            continue
    return out


def first_file_manager_uuid_from_url(url: str | None) -> Optional[UUID]:
    """Best-effort single UUID from a file URL (legacy helper behavior)."""
    found = extract_file_manager_uuids_from_text(url or "")
    return next(iter(found), None)


def collect_gdpr_file_manager_ids_from_messages(messages: Sequence[Any] | None) -> set[UUID]:
    """Gather File Manager file UUIDs referenced by transcript rows.

    - ``type == "file"``: parse ``text`` as JSON for ``file_id`` and ``url``.
    - Any message: scan ``text`` for File Manager URL patterns (covers pasted
      links and malformed JSON).
    """
    ids: set[UUID] = set()
    for msg in messages or []:
        text = getattr(msg, "text", None) or ""
        msg_type = (getattr(msg, "type", None) or "").lower()
        if msg_type == "file":
            try:
                payload = json.loads(text)
                if isinstance(payload, dict):
                    raw_fid = payload.get("file_id")
                    if raw_fid:
                        try:
                            ids.add(UUID(str(raw_fid)))
                        except (ValueError, TypeError):
                            pass
                    url = payload.get("url")
                    if isinstance(url, str):
                        ids |= extract_file_manager_uuids_from_text(url)
            except (json.JSONDecodeError, TypeError):
                pass
        ids |= extract_file_manager_uuids_from_text(text)
    return ids


def collect_gdpr_file_manager_ids_from_transcription_field(
    transcription: str | None,
) -> set[UUID]:
    """Legacy ``conversations.transcription`` may embed file-manager URLs."""
    return extract_file_manager_uuids_from_text(transcription)


def collect_gdpr_file_manager_ids_from_custom_attributes(
    custom_attributes: dict | None,
) -> set[UUID]:
    """Scan JSON-serialized ``custom_attributes`` for file-manager URLs."""
    if not custom_attributes:
        return set()
    try:
        blob = json.dumps(custom_attributes, ensure_ascii=False, default=str)
    except TypeError:
        return set()
    return extract_file_manager_uuids_from_text(blob)
