"""Reading the result of loading a document into a knowledge base."""

import datetime
import os
from typing import Any, Mapping, Optional
from urllib.parse import urlparse

ERRORS_SHOWN = 5
SUCCESSFUL_SYNC_STATUSES = ("success", "success_with_warnings")
INDEXING_STATUS = "indexing"
SYNC_RESULT_FIELDS = ("last_synced", "last_sync_status", "last_sync_error", "last_successful_sync")


class DocumentNotLoadedError(Exception):
    """No store of the knowledge base took the document."""


class KnowledgeBaseUnavailableError(Exception):
    """The stores of the knowledge base could not be reached."""


def has_text(content: Optional[str]) -> bool:
    """True when there is text to load; extractors return blank text for unreadable files."""
    return bool((content or "").strip())


def ensure_has_text(content: Optional[str], document_name: str) -> None:
    """Raise when there is no text to load, so the document counts as failed."""
    if not has_text(content):
        raise DocumentNotLoadedError(f"{document_name} has no readable text")


def stores_missed(result: Optional[Mapping[str, bool]]) -> list[str]:
    """The stores that did not take the document."""
    return [store for store, loaded in (result or {}).items() if not loaded]


def ensure_loaded(result: Optional[Mapping[str, bool]], document_name: str) -> None:
    """Raise when no store took the document; an empty result means the stores could not be reached."""
    if not result:
        raise KnowledgeBaseUnavailableError(f"{document_name} was not loaded into the knowledge base (no store reached)")
    if not any(result.values()):
        refused_by = ", ".join(stores_missed(result))
        raise DocumentNotLoadedError(f"{document_name} was not loaded into the knowledge base ({refused_by})")


def missed_stores_warning(result: Optional[Mapping[str, bool]], document_name: str) -> Optional[str]:
    """A warning naming the stores that did not take a document the other stores took."""
    missed = stores_missed(result)
    if not missed:
        return None
    return f"{document_name} was loaded but is missing from: {', '.join(missed)}"


async def load_document(
    rag_manager: Any,
    kb: Any,
    doc_id: str,
    content: str,
    metadata: dict,
    document_name: str,
    legra_finalize: bool = False,
) -> Optional[str]:
    """Add a document to the knowledge base; raises when no store took it, returns a warning when only some did."""
    result = await rag_manager.add_document(kb, doc_id, content, metadata, legra_finalize=legra_finalize)
    ensure_loaded(result, document_name)
    return missed_stores_warning(result, document_name)


def article_sync_outcome(attempted: int, copied: int, errors: list[str], had_articles: bool) -> tuple[str, str]:
    """The sync status and message: error when nothing was copied and no articles were found before the run."""
    if not errors:
        return "success", ""
    details = "; ".join(errors[:ERRORS_SHOWN])
    failed = attempted - copied
    if failed > 0:
        details = f"{failed} of {attempted} articles could not be copied: {details}"
    nothing_copied_and_none_found = attempted > 0 and copied == 0 and not had_articles
    return ("error" if nothing_copied_and_none_found else "success_with_warnings"), details


def sync_result_fields(status: str, error: str = "", now: Optional[datetime.datetime] = None) -> dict[str, Any]:
    """The KB fields a sync writes: last_synced on every run, last_successful_sync only when it succeeded."""
    now = now or datetime.datetime.now()
    fields: dict[str, Any] = {"last_synced": now, "last_sync_status": status, "last_sync_error": error}
    if status in SUCCESSFUL_SYNC_STATUSES:
        fields["last_successful_sync"] = now
    return fields


def indexing_started_fields(now: Optional[datetime.datetime] = None) -> dict[str, Any]:
    """The KB fields a save writes when it starts indexing; they replace the outcome of the previous indexing."""
    return {"last_synced": now or datetime.datetime.now(), "last_sync_status": INDEXING_STATUS, "last_sync_error": ""}


def document_label(document_id: str) -> str:
    """A short name for a document of a saved knowledge base: its file name, or the part it stands for."""
    _, _, part = document_id.partition("#")
    if not part:
        return "The knowledge base"
    if not part.startswith("file_"):
        return "The content"
    position, _, location = part.partition(":")
    file_name = os.path.basename(urlparse(location).path)
    return file_name or f"File {int(position.removeprefix('file_')) + 1}"


def _document_problem(entry: Mapping[str, Any]) -> tuple[Optional[str], bool]:
    """What went wrong with one loaded document, if anything, and whether a store took it."""
    name = entry.get("name") or document_label(str(entry.get("id") or ""))
    if entry.get("error"):
        return f"{name}: {entry['error']}", False
    try:
        ensure_loaded(entry.get("result"), name)
    except (DocumentNotLoadedError, KnowledgeBaseUnavailableError) as error:
        return str(error), False
    return missed_stores_warning(entry.get("result"), name), True


def indexing_outcome(results: list[Mapping[str, Any]]) -> tuple[str, str]:
    """The status and message after indexing a saved knowledge base: error when no document was stored."""
    if not results:
        return "error", "Nothing was indexed"
    outcomes = [_document_problem(entry) for entry in results]
    problems = [problem for problem, _ in outcomes if problem]
    indexed = sum(1 for _, was_stored in outcomes if was_stored)
    status, _ = article_sync_outcome(len(results), indexed, problems, had_articles=False)
    if not problems:
        return status, ""
    details = "; ".join(problems[:ERRORS_SHOWN])
    failed = len(results) - indexed
    return status, f"{failed} of {len(results)} documents could not be indexed: {details}" if failed else details
