import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID
from croniter import croniter, CroniterBadCronError
from celery import shared_task
from app.modules.data.utils import FileTextExtractor
from app.dependencies.injector import injector
from app.modules.data.manager import AgentRAGServiceManager
from app.schemas.agent_knowledge import KBCreate
from app.services.agent_knowledge import KnowledgeBaseService
from app.services.datasources import DataSourceService
from app.modules.integration.office365_connector import Office365Connector
from app.services.app_settings import AppSettingsService
from app.core.utils.encryption_utils import decrypt_key

logger = logging.getLogger(__name__)


# Helper function removed - now using simplified manager


# ------------------------------ Helpers --------------------------------- #
def _compute_next_run(cron_expr: Optional[str], last_synced: Optional[datetime]) -> Optional[datetime]:
    """
    Validate cron expression and compute the next run as a datetime.
    Returns None if invalid.
    """
    if not cron_expr or not isinstance(cron_expr, str):
        return None
    expr = cron_expr.strip()
    try:
        if not croniter.is_valid(expr):
            raise CroniterBadCronError(f"Invalid cron: {expr!r}")
        if last_synced is None:
            return datetime.now(timezone.utc)
        start = last_synced
        it = croniter(expr, start_time=start)
        return it.get_next(datetime)  # get a datetime directly
    except Exception as e:
        logger.error(f"Cron invalid -> {expr!r}: {e}")
        return None

# ------------------------------ Task entrypoints --------------------------------- #


@shared_task
def import_sharepoint_files_to_kb():
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(import_sharepoint_files_to_kb_async_with_scope())


async def import_sharepoint_files_to_kb_async_with_scope():
    """Wrapper to run SharePoint import for all tenants"""
    from app.tasks.base import run_task_with_tenant_support
    return await run_task_with_tenant_support(
        import_sharepoint_files_to_kb_async,
        "SharePoint file import"
    )


async def import_sharepoint_files_to_kb_async(kb_id: Optional[UUID] = None):
    logger.info("Starting SharePoint file import...")

    # AgentRAGService is now created on-demand per knowledge base
    kb_service = injector.get(KnowledgeBaseService)
    rag_manager = injector.get(AgentRAGServiceManager)
    app_settings_service = injector.get(AppSettingsService)

    kb_list = [await kb_service.get_by_id(kb_id)] if kb_id else await kb_service.get_all()

    processed_ds = 0
    files_added_tot = 0
    files_deleted_tot = 0
    errors = []

    for kb in kb_list:
        try:
            if not kb.sync_active or not kb.sync_source_id:
                continue

            ds = await injector.get(DataSourceService).get_by_id(kb.sync_source_id, True)
            if not ds or ds.source_type.lower() != "o365":
                continue

            # Get app_settings_id from data source connection_data
            conn_data = ds.connection_data
            app_settings_id = conn_data.get("app_settings_id")
            if not app_settings_id:
                msg = f"{kb.id} app_settings_id not found in data source"
                logger.warning(msg)
                errors.append(msg)
                continue

            # Get Microsoft credentials from app settings by ID
            try:
                app_settings = await app_settings_service.get_by_id(UUID(app_settings_id))
                values = app_settings.values if isinstance(
                    app_settings.values, dict) else {}
                o365_client_id = values.get("microsoft_client_id")
                o365_client_secret = values.get("microsoft_client_secret")
                o365_tenant_id = values.get("microsoft_tenant_id")

                # Decrypt client_secret
                if o365_client_secret:
                    o365_client_secret = decrypt_key(o365_client_secret)

                if not o365_client_id or not o365_client_secret or not o365_tenant_id:
                    msg = f"{kb.id} Microsoft credentials incomplete in app settings"
                    logger.warning(msg)
                    errors.append(msg)
                    continue
            except Exception as e:
                msg = f"{kb.id} failed to get app settings: {str(e)}"
                logger.error(msg)
                errors.append(msg)
                continue

            # ---- schedule gate ----
            expr = (kb.sync_schedule or "").strip()
            next_run_time = _compute_next_run(expr, kb.last_synced)
            if not next_run_time:
                msg = f"{kb.id} invalid cron: {expr!r}"
                logger.warning(msg)
                errors.append(msg)
                continue

            now = datetime.now(timezone.utc)
            if now < next_run_time:
                # Not yet time to run
                continue

            # ---- SharePoint client ----
            try:
                sp_client = Office365Connector(
                    sharepoint_url=kb.url,
                    client_id=o365_client_id,
                    tenant_id=o365_tenant_id,
                    client_secret=o365_client_secret,
                    refresh_token=conn_data["refresh_token"],
                    redirect_uri=conn_data["redirect_uri"],
                )
            except Exception as e:
                logger.error(f"Failed to initialize SharePoint client: {e}")
                errors.append(f"{kb.id} SharePoint init failed: {str(e)}")
                continue

            # ---- enumerate files ----
            try:
                result = sp_client.list_files()
            except Exception as e:
                logger.error(f"Failed to list files: {e}")
                errors.append(f"{kb.id} file listing failed: {str(e)}")
                continue

            # Get existing documents using simplified manager
            existing_files = await rag_manager.get_document_ids(kb)

            new_files = [
                f
                for f in result.get("files", [])
                if not any(existing.startswith(f"KB:{kb.id}#{f['path']}") for existing in existing_files)
            ]

            deleted_files = [
                existing
                for existing in existing_files
                if not any(existing.startswith(f"KB:{kb.id}#{f['path']}") for f in result.get("files", []))
            ]

            # ---- delete removed files ----
            for filename in deleted_files:
                try:
                    await rag_manager.delete_document(kb, filename)
                    files_deleted_tot += 1
                except Exception as e:
                    logger.error(f"Delete failed {filename}: {e}")
                    errors.append(f"Delete failed {filename}: {str(e)}")

            # ---- add new files ----
            for file_info in new_files:
                try:
                    file_content = sp_client.get_file_content(
                        file_info["download_url"])
                    if len(file_content) == 0:
                        logger.warning(
                            f"File {file_info.get('name', '')} has no content, skipping...")
                        continue

                    # Use the filename's suffix to indentify the type (e.g., .docx)
                    extracted_text = FileTextExtractor().extract_from_bytes(
                        filename=file_info.get("name", ""),
                        content=file_content,
                    )

                    # add doc to RAG
                    doc_id = f"KB:{kb.id}#{file_info['path']}"
                    metadata = {
                        "name": file_info.get("name", ""),
                        "description": f"Imported from SharePoint: {file_info.get('path', '')}",
                        "kb_id": str(kb.id),
                    }

                    # Add to knowledge base using simplified manager
                    await rag_manager.add_document(kb, doc_id, extracted_text, metadata)
                    files_added_tot += 1

                except Exception as e:
                    logger.error(
                        f"Error processing {file_info.get('path', '<unknown>')}: {e}")
                    errors.append(
                        f"Error processing {file_info.get('path', '<unknown>')}: {str(e)}")

            # ---- update KB sync timestamps ----
            kb_update = json.loads(kb.model_dump_json())
            kb_update["last_synced"] = datetime.now(timezone.utc)
            kb_update["last_file_date"] = datetime.now(timezone.utc)
            await kb_service.update(kb.id, KBCreate(**kb_update))

            processed_ds += 1

        except Exception as e:
            # don't let one KB kill the whole batch
            logger.error(
                f"Unhandled error for KB {getattr(kb, 'id', '<unknown>')}: {e}")
            errors.append(
                f"{getattr(kb, 'id', '<unknown>')} unhandled error: {str(e)}")
            continue

    return {
        "status": "completed",
        "files_added": files_added_tot,
        "files_deleted": files_deleted_tot,
        "datasources_processed": processed_ds,
        "errors": errors or None,
    }
