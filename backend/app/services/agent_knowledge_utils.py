import asyncio
import logging
from uuid import UUID
from typing import Any

from app.modules.data.manager import AgentRAGServiceManager
from app.schemas.agent_knowledge import KBRead
from app.services.file_manager import FileManagerService
from app.db.models.file import StorageProvider


logger = logging.getLogger(__name__)


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
        rag_manager.load_knowledge_items([kb_item], action=action)
    )

    def _log_task_result(t: asyncio.Task) -> None:
        try:
            t.result()
        except Exception:
            logger.exception("RAG %s task failed", action)

    task.add_done_callback(_log_task_result)

