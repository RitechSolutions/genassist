import asyncio
import datetime
import logging
from uuid import UUID
from typing import Any, Optional

from sqlalchemy import select

from app.core.tenant_scope import get_tenant_context
from app.db.models import KnowledgeBaseModel
from app.modules.data.load_result import (
    INDEXING_STATUS,
    indexing_outcome,
    indexing_started_fields,
    sync_result_fields,
)
from app.modules.data.manager import SAVE_INDEXED_KB_TYPES, AgentRAGServiceManager
from app.modules.data.service import capped_failure_text
from app.schemas.agent_knowledge import KBBase, KBRead
from app.services.file_manager import FileManagerService
from app.db.models.file import StorageProvider


logger = logging.getLogger(__name__)

INDEXING_STOPPED_MESSAGE = "Indexing stopped because of an unexpected error"
OUTCOME_WRITE_ATTEMPTS = 5
OUTCOME_RETRY_SECONDS = 1.0
OWN_SAVE = "own_save"
NEWER_SAVE = "newer_save"
SAVE_NOT_VISIBLE = "save_not_visible"


class IndexingOutcomeNotRecorded(Exception):
    """The outcome of an indexing could not be written on its knowledge base."""


async def populate_remote_file_metadata(
    kb_item: KBRead,
    file_manager_service: FileManagerService,
) -> None:
    """
    For any files attached to a KB item that are managed by a non-local storage
    provider, populate `storage_provider` and `file_url` so the client has
    direct access to the stored file.
    """
    if not getattr(kb_item, "files", None):
        return

    for file in kb_item.files:
        if not (isinstance(file, dict) and file.get("file_id")):
            continue

        file_id: Any = file.get("file_id")
        file_obj = await file_manager_service.get_file_by_id(UUID(str(file_id)))
        if file_obj and file_obj.storage_provider != StorageProvider.LOCAL:
            file["storage_provider"] = file_obj.storage_provider
            # get the file url from the storage provider
            file["file_url"] = await file_manager_service.get_file_url(file_obj)


def mark_indexing_started(item: KBBase) -> None:
    """Set the indexing status of a knowledge base that is indexed on save; the values the client sent are dropped."""
    if item.type not in SAVE_INDEXED_KB_TYPES:
        return
    item.last_successful_sync = None
    for field, value in indexing_started_fields().items():
        setattr(item, field, value)


async def _indexing_result(rag_manager: AgentRAGServiceManager, kb_item: KBRead, action: str) -> tuple[str, str]:
    """Index the saved knowledge base; returns the status and message to keep on it."""
    try:
        results = await rag_manager.load_knowledge_items([kb_item], action=action)
    except Exception:
        logger.exception("RAG %s task failed", action)
        return "error", INDEXING_STOPPED_MESSAGE
    status, message = indexing_outcome(results)
    return status, capped_failure_text(message)


def _instant(moment: Optional[datetime.datetime]) -> Optional[datetime.datetime]:
    """The moment in UTC; one without a time zone is local time, which is how the database driver stores it."""
    return moment.astimezone(datetime.timezone.utc) if moment is not None else None


def save_seen_on_row(row: Any, started_kb: KBRead) -> str:
    """Whether the row shows the save that started this indexing, a newer one, or does not show it yet."""
    saved_at = _instant(started_kb.last_synced)
    row_saved_at = _instant(row.last_synced) if row is not None else None
    if saved_at is None:
        return NEWER_SAVE
    if row_saved_at is None or row_saved_at < saved_at:
        return SAVE_NOT_VISIBLE
    return OWN_SAVE if row_saved_at == saved_at else NEWER_SAVE


async def _locked_kb_row(db: Any, kb_id: UUID) -> Optional[KnowledgeBaseModel]:
    """Re-read the knowledge base row, locked for a write, so no save can change it before the outcome is in."""
    statement = (
        select(KnowledgeBaseModel)
        .where(KnowledgeBaseModel.id == kb_id)
        .execution_options(populate_existing=True)
        .with_for_update(key_share=True)
    )
    return (await db.execute(statement)).scalars().first()


def _write_outcome(row: KnowledgeBaseModel, status: str, message: str) -> bool:
    """Set the outcome on a row that still waits for it; False when the row changed type or status meanwhile."""
    still_waits_for_outcome = row.type in SAVE_INDEXED_KB_TYPES and row.last_sync_status == INDEXING_STATUS
    if not still_waits_for_outcome:
        return False
    for field, value in sync_result_fields(status, message).items():
        setattr(row, field, value)
    return True


async def record_indexing_outcome(started_kb: KBRead, status: str, message: str) -> None:
    """Write how the indexing ended, only onto the row state left by the save that started it."""
    from app.dependencies.injector import injector
    from app.services.agent_knowledge import KnowledgeBaseService

    repository = injector.get(KnowledgeBaseService).repository
    for attempt in range(OUTCOME_WRITE_ATTEMPTS):
        if attempt > 0:
            await asyncio.sleep(OUTCOME_RETRY_SECONDS)
        row = await _locked_kb_row(repository.db, started_kb.id)
        seen = save_seen_on_row(row, started_kb)
        if seen == OWN_SAVE:
            if _write_outcome(row, status, message):
                await repository.update(row)
            else:
                logger.info(f"Indexing outcome of KB {started_kb.id} not kept: its type or status changed meanwhile")
            return
        if seen == NEWER_SAVE:
            logger.info(f"Indexing outcome of KB {started_kb.id} not kept: the knowledge base was saved again")
            return
        # The save may not be committed yet: release the row before looking again.
        await repository.db.rollback()
    raise IndexingOutcomeNotRecorded(
        f"the save that started the indexing was not found in {OUTCOME_WRITE_ATTEMPTS} reads"
    )


async def index_saved_knowledge_base(
    rag_manager: AgentRAGServiceManager, kb_item: KBRead, action: str, tenant_id: str | None
) -> None:
    """Index the knowledge base after a save and keep the outcome on it."""
    from app.tasks.base import run_task_for_tenant

    status, message = await _indexing_result(rag_manager, kb_item, action)
    if kb_item.type not in SAVE_INDEXED_KB_TYPES:
        return
    outcome = {"started_kb": kb_item, "status": status, "message": message}
    written = await run_task_for_tenant(record_indexing_outcome, "Record KB indexing outcome", tenant_id, **outcome)
    if written.get("status") != "success":
        logger.error(
            f"Could not record the indexing outcome ({status}) of KB {kb_item.id}; "
            f"its status stays Indexing until it is saved again: {written.get('error')}"
        )


def schedule_rag_load(
    rag_manager: AgentRAGServiceManager,
    kb_item: KBRead,
    action: str,
) -> None:
    """
    Fire-and-forget background load into RAG with consistent error logging.

    This helper is intentionally lightweight so it can be reused by multiple
    routers or services without pulling in FastAPI-specific concepts.
    """
    task = asyncio.create_task(
        index_saved_knowledge_base(rag_manager, kb_item, action, get_tenant_context())
    )

    def _log_task_result(t: asyncio.Task) -> None:
        try:
            t.result()
        except Exception:
            logger.exception("RAG %s task failed", action)

    task.add_done_callback(_log_task_result)

