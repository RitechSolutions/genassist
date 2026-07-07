from __future__ import annotations

import hashlib
import re
from typing import Iterable


def normalize_title(title: str) -> str:
    lowered = title.lower().strip()
    return re.sub(r"[^a-z0-9]+", " ", lowered).strip()


def compute_fingerprint(
    title: str,
    ticket_type: str,
    tags: Iterable[str] | None = None,
    error_signature: str | None = None,
) -> str:
    """Stable hash for duplicate detection (Sentry-style grouping)."""
    parts = [ticket_type.strip().lower(), normalize_title(title)]
    if tags:
        parts.append(",".join(sorted(t.strip().lower() for t in tags if t.strip())))
    if error_signature:
        parts.append(error_signature.strip().lower()[:200])
    raw = "|".join(parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]
