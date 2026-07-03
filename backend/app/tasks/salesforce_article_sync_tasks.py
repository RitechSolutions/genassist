import json
import logging
import re
from datetime import datetime
from typing import Any, List, Optional
from uuid import UUID

from celery import shared_task
from croniter import croniter

from app.core.utils.encryption_utils import decrypt_key
from app.dependencies.injector import injector
from app.modules.data.manager import AgentRAGServiceManager
from app.modules.integration.salesforce import SalesforceConnector
from app.schemas.agent_knowledge import KBCreate
from app.schemas.dynamic_form_schemas.app_settings_schemas import (
    get_encrypted_fields_for_type,
)
from app.services.agent_knowledge import KnowledgeBaseService
from app.services.app_settings import AppSettingsService
from app.services.datasources import DataSourceService

logger = logging.getLogger(__name__)


def _kb_update_dict(kb: Any) -> dict[str, Any]:
    """ORM/Pydantic KB row to a dict suitable for KBCreate(**payload)."""
    return json.loads(kb.model_dump_json())


async def _resolve_salesforce_credentials(app_settings_id: Any) -> dict[str, Any]:
    """Resolve and decrypt SalesForce credentials from App Settings (Config Vars).

    Mirrors ``SalesforceToolNode``: fetch the App Settings entry by id, then decrypt any
    encrypted fields (the client secret) before use.
    """
    app_settings_service = injector.get(AppSettingsService)
    app_settings = await app_settings_service.get_by_id(UUID(str(app_settings_id)))
    values = app_settings.values if isinstance(app_settings.values, dict) else {}
    encrypted_fields = set(get_encrypted_fields_for_type(app_settings.type))
    return {
        key: (
            decrypt_key(value)
            if key in encrypted_fields and isinstance(value, str) and value
            else value
        )
        for key, value in values.items()
    }


@shared_task
def import_salesforce_articles_to_kb(kb_id: Optional[str] = None, sync_now: bool = False):
    """
    Import articles from SalesForce Knowledge into the knowledge base.
    When kb_id is provided, sync only that KB. Otherwise sync all KBs due for sync.
    sync_now: when True, bypass schedule and force immediate sync.
    """
    # 15min timeout mirrors the Zendesk sync: beat fires every 15min with expires=900s, so a
    # hung run is force-cancelled before the next tick could enqueue a duplicate, bounding any
    # single sync so a hung downstream call (RAG/embeddings/pgvector) cannot wedge the worker.
    from app.tasks.base import run_async_in_celery

    return run_async_in_celery(
        import_salesforce_articles_to_kb_async_with_scope(kb_id=kb_id, sync_now=sync_now),
        timeout=15 * 60,
        task_name="import_salesforce_articles_to_kb",
    )


async def import_salesforce_articles_to_kb_async_with_scope(
    kb_id: Optional[str] = None, sync_now: bool = False
):
    """Wrapper to run SalesForce article import for all tenants."""
    from app.tasks.base import run_task_with_tenant_support

    result = await run_task_with_tenant_support(
        import_salesforce_articles_to_kb_async,
        "SalesForce article import",
        kb_id=UUID(kb_id) if kb_id else None,
        sync_now=sync_now,
    )
    if result.get("status") == "completed":
        logger.info(f"Results: {result.get('per_kb')}")
    return result


async def import_salesforce_articles_to_kb_async(
    kb_id: Optional[UUID] = None, sync_now: bool = False
):
    """Async implementation of SalesForce Knowledge article import.

    Persists ``last_synced``, ``last_sync_status``, and ``last_sync_error`` on the KB row so
    the UI can show outcome. Returns aggregate counts plus ``per_kb`` for API responses.

    Note: ``KnowledgeBaseService.update`` uses ``exclude_none=True``; use ``last_sync_error=""``
    to clear a previous error on success.
    """
    logger.info("Starting SalesForce article import...")

    kb_service = injector.get(KnowledgeBaseService)
    rag_manager = injector.get(AgentRAGServiceManager)

    per_kb: List[dict[str, Any]] = []

    if not kb_id:
        kbList = await kb_service.get_all(kb_type="salesforce")
    else:
        from app.core.exceptions.exception_classes import AppException

        try:
            single = await kb_service.get_by_id(kb_id)
        except AppException:
            res = {
                "status": "failed",
                "error": f"Knowledge base {kb_id} not found",
                "articles_added": 0,
                "articles_deleted": 0,
                "articles_updated": 0,
                "datasources_processed": 0,
                "per_kb": [
                    {
                        "kb_id": str(kb_id),
                        "status": "failed",
                        "reason": "not_found",
                    }
                ],
            }
            logger.warning(res["error"])
            return res
        if single.type != "salesforce":
            res = {
                "status": "failed",
                "error": f"Knowledge base {kb_id} is not a SalesForce type (got {single.type!r})",
                "articles_added": 0,
                "articles_deleted": 0,
                "articles_updated": 0,
                "datasources_processed": 0,
                "per_kb": [
                    {
                        "kb_id": str(kb_id),
                        "name": single.name,
                        "status": "failed",
                        "reason": "wrong_kb_type",
                        "type": single.type,
                    }
                ],
            }
            logger.warning(res["error"])
            return res
        kbList = [single]

    if not kbList:
        return {
            "status": "completed",
            "message": "No SalesForce knowledge bases to process",
            "articles_added": 0,
            "articles_deleted": 0,
            "articles_updated": 0,
            "datasources_processed": 0,
            "per_kb": [],
        }

    processed_ds = 0
    articles_added_tot = 0
    articles_deleted_tot = 0
    articles_updated_tot = 0
    last_file_date = None

    for kb in kbList:
        logger.info(f"Processing knowledge base {kb.name}")
        # Reset per-KB so one KB's newest article date can't leak onto another KB in a
        # multi-KB (scheduled) run.
        last_file_date = None

        if not sync_now and (kb.sync_active == 0 or not kb.sync_source_id):
            logger.info(
                f"Knowledge base {kb.id} is not active or does not have a sync source"
            )
            per_kb.append(
                {
                    "kb_id": str(kb.id),
                    "name": kb.name,
                    "status": "skipped",
                    "reason": "sync_inactive_or_no_source",
                }
            )
            continue

        ds = await injector.get(DataSourceService).get_by_id(kb.sync_source_id, True)
        if not ds:
            logger.info(f"Knowledge base {kb.id} has no sync source")
            per_kb.append(
                {
                    "kb_id": str(kb.id),
                    "name": kb.name,
                    "status": "skipped",
                    "reason": "datasource_not_found",
                }
            )
            continue

        if ds.source_type.lower() != "salesforce":
            logger.info(
                f"Knowledge base {kb.id} has a sync source that is not SalesForce ({ds.source_type})"
            )
            if sync_now or kb_id is not None:
                ku = _kb_update_dict(kb)
                ku["last_synced"] = datetime.now()
                ku["last_sync_status"] = "error"
                ku["last_sync_error"] = (
                    f"Sync source is not SalesForce (type={ds.source_type})"
                )
                await kb_service.update(kb.id, KBCreate(**ku))
            per_kb.append(
                {
                    "kb_id": str(kb.id),
                    "name": kb.name,
                    "status": "skipped",
                    "reason": "datasource_not_salesforce",
                    "source_type": ds.source_type,
                }
            )
            continue

        # When sync_now or kb_id provided, bypass cron schedule check
        force_sync = sync_now or (kb_id is not None)
        cron_string = kb.sync_schedule
        if not cron_string and not force_sync:
            logger.info(f"Knowledge base {kb.id} has no sync schedule")
            per_kb.append(
                {
                    "kb_id": str(kb.id),
                    "name": kb.name,
                    "status": "skipped",
                    "reason": "no_sync_schedule",
                }
            )
            continue
        if not force_sync:
            cron_iter = croniter(cron_string)
            next_run_time = datetime.now()
            if kb.last_synced:
                logger.info("Getting next run time from last synced")
                next_run_time = cron_iter.get_next(start_time=kb.last_synced)
                next_run_time = datetime.fromtimestamp(next_run_time)
                logger.info(
                    f"Knowledge base {kb.id} last synced at {kb.last_synced}, next run time: {next_run_time}"
                )

            if datetime.now() < next_run_time:
                logger.info(
                    f"Knowledge base {kb.id} is not due for sync, next sync at {next_run_time}"
                )
                per_kb.append(
                    {
                        "kb_id": str(kb.id),
                        "name": kb.name,
                        "status": "skipped",
                        "reason": "not_due_per_schedule",
                        "next_sync_at": next_run_time.isoformat(),
                    }
                )
                continue

        if not ds.connection_data:
            logger.info(
                f"Knowledge base {kb.id} has no connection data for sync source {ds.name}"
            )
            if sync_now or kb_id is not None:
                ku = _kb_update_dict(kb)
                ku["last_synced"] = datetime.now()
                ku["last_sync_status"] = "error"
                ku["last_sync_error"] = "SalesForce datasource has no connection data"
                await kb_service.update(kb.id, KBCreate(**ku))
            per_kb.append(
                {
                    "kb_id": str(kb.id),
                    "name": kb.name,
                    "status": "skipped",
                    "reason": "no_connection_data",
                }
            )
            continue

        conn_data = ds.connection_data

        app_settings_id = conn_data.get("app_settings_id")
        content_field = conn_data.get("content_field")
        language = conn_data.get("language") or None  # Optional
        data_category = conn_data.get("data_category") or None  # Optional

        if not app_settings_id or not content_field:
            err = "Incomplete SalesForce connection (app_settings_id and content_field required)"
            logger.error(f"Knowledge base {kb.id}: {err}")
            ku = _kb_update_dict(kb)
            ku["last_synced"] = datetime.now()
            ku["last_sync_status"] = "error"
            ku["last_sync_error"] = err
            await kb_service.update(kb.id, KBCreate(**ku))
            per_kb.append(
                {
                    "kb_id": str(kb.id),
                    "name": kb.name,
                    "status": "error",
                    "reason": "incomplete_connection_data",
                }
            )
            continue

        try:
            # Resolve credentials from App Settings (Config Vars) exactly like the Case node.
            values = await _resolve_salesforce_credentials(app_settings_id)
            salesforce_connector = SalesforceConnector(
                instance_url=values.get("salesforce_instance_url"),
                client_id=values.get("salesforce_client_id"),
                client_secret=values.get("salesforce_client_secret"),
            )

            fetched_articles = await salesforce_connector.fetch_knowledge_articles(
                content_field=content_field,
                language=language,
                data_category=data_category,
            )

            allow_html_content = kb.extra_metadata.get("allow_html_content") or False

            # Parse article body based on allow_html_content flag
            def _parse_article_body(article: dict) -> str:
                if not allow_html_content and article.get("body"):
                    return re.sub(r"<[^>]*>", "", article.get("body", ""))
                return article.get("body", "") or ""

            articles = list(fetched_articles)

            if not articles:
                logger.info(
                    f"No articles found in SalesForce for datasource {ds.name}"
                )
                processed_ds += 1
                ku = _kb_update_dict(kb)
                ku["last_synced"] = datetime.now()
                ku["last_sync_status"] = "success"
                ku["last_sync_error"] = ""
                await kb_service.update(kb.id, KBCreate(**ku))
                per_kb.append(
                    {
                        "kb_id": str(kb.id),
                        "name": kb.name,
                        "status": "success",
                        "articles_added": 0,
                        "articles_updated": 0,
                        "articles_deleted": 0,
                        "note": "no_articles_from_salesforce",
                    }
                )
                continue

            articles_added = 0
            articles_deleted = 0
            articles_updated = 0
            kb_errors = []

            logger.info("Getting existing articles from RAG...")
            existing_articles = await rag_manager.get_document_ids(kb)
            logger.info(
                f"Found {len(existing_articles)} existing articles in RAG for knowledge base {kb.id}"
            )

            # Create a set of article IDs from SalesForce
            salesforce_article_ids = {
                f"KB:{str(kb.id)}#article_{article['id']}" for article in articles
            }

            # Find new articles
            new_articles = [
                article
                for article in articles
                if f"KB:{str(kb.id)}#article_{article['id']}" not in existing_articles
            ]
            logger.info(
                f"Found {len(new_articles)} new articles to process for knowledge base {kb.id}"
            )

            # Find deleted articles (exist in RAG but not in SalesForce)
            deleted_article_ids = [
                article_id
                for article_id in existing_articles
                if article_id.startswith(f"KB:{str(kb.id)}#article_")
                and article_id not in salesforce_article_ids
            ]
            logger.info(
                f"Found {len(deleted_article_ids)} deleted articles to remove for knowledge base {kb.id}"
            )

            # Load last-known updated_at per article from KB extra_metadata (skip-if-unchanged)
            article_updated_at_key = "salesforce_article_updated_at"
            stored_updated_at: dict = (kb.extra_metadata or {}).get(
                article_updated_at_key
            ) or {}
            # Work on a copy so we can persist it after add/update/delete
            article_updated_at_map = dict(stored_updated_at)

            def _is_article_edited(article: dict) -> bool:
                """True if we have no stored updated_at or SalesForce's is newer."""
                aid = str(article["id"])
                sf_updated = article.get("updated_at") or ""
                if not sf_updated:
                    return True  # unknown freshness, treat as edited to be safe
                stored = stored_updated_at.get(aid)
                if not stored:
                    return True  # first time we've seen it in stored state
                # ISO8601 strings compare correctly as strings
                return sf_updated > stored

            # Find updated articles (exist in both AND edited in SalesForce since last sync)
            updated_articles = []
            for article in articles:
                article_id = f"KB:{str(kb.id)}#article_{article['id']}"
                if article_id in existing_articles and _is_article_edited(article):
                    updated_articles.append(article)
            skipped_unchanged = sum(
                1
                for a in articles
                if f"KB:{str(kb.id)}#article_{a['id']}" in existing_articles
                and not _is_article_edited(a)
            )
            if skipped_unchanged:
                logger.info(
                    f"Skipping {skipped_unchanged} existing articles (unchanged) for knowledge base {kb.id}"
                )

            # Delete removed articles from RAG and from our updated_at map
            article_id_prefix = f"KB:{str(kb.id)}#article_"
            if deleted_article_ids:
                for doc_id in deleted_article_ids:
                    try:
                        logger.info(f"Deleting article {doc_id} from RAG...")
                        await rag_manager.delete_document(kb, doc_id)
                        articles_deleted += 1
                        if doc_id.startswith(article_id_prefix):
                            sf_id = doc_id[len(article_id_prefix) :]
                            article_updated_at_map.pop(sf_id, None)
                    except Exception as e:
                        error_msg = f"Error deleting article {doc_id}: {str(e)}"
                        logger.error(error_msg)
                        kb_errors.append(error_msg)
                        continue

            def _build_content_and_metadata(article: dict) -> tuple[str, dict]:
                article_title = article.get("title") or "Untitled Article"
                article_summary = article.get("summary") or ""
                article_body = _parse_article_body(article)
                parts = [article_title]
                if article_summary:
                    parts.append(article_summary)
                if article_body:
                    parts.append(article_body)
                content = "\n\n".join(parts)
                metadata = {
                    "name": article_title,
                    "description": f"SalesForce article from {ds.name}",
                    "kb_id": str(kb.id),
                    "article_id": str(article["id"]),
                    "language": language or "",
                }
                return content, metadata

            # Add new articles to RAG
            for article in new_articles:
                try:
                    article_id = f"KB:{str(kb.id)}#article_{article['id']}"
                    content, metadata = _build_content_and_metadata(article)

                    res = await rag_manager.add_document(
                        kb, article_id, content, metadata
                    )
                    logger.info(f"Article {metadata['name']} processed with result: {res}")
                    articles_added += 1
                    if article.get("updated_at"):
                        article_updated_at_map[str(article["id"])] = article["updated_at"]

                    # Track last file date
                    updated_at = article.get("updated_at")
                    if updated_at:
                        try:
                            article_date = datetime.fromisoformat(
                                updated_at.replace("Z", "+00:00")
                            )
                            if not last_file_date or article_date > last_file_date:
                                last_file_date = article_date
                        except Exception:
                            pass

                except Exception as e:
                    error_msg = f"Error processing article {article.get('id')}: {str(e)}"
                    logger.error(error_msg)
                    kb_errors.append(error_msg)
                    continue

            # Update existing articles
            for article in updated_articles:
                try:
                    article_id = f"KB:{str(kb.id)}#article_{article['id']}"
                    content, metadata = _build_content_and_metadata(article)

                    # Delete and re-add to update
                    await rag_manager.delete_document(kb, article_id)
                    res = await rag_manager.add_document(
                        kb, article_id, content, metadata
                    )
                    logger.info(f"Article {metadata['name']} updated with result: {res}")
                    articles_updated += 1
                    if article.get("updated_at"):
                        article_updated_at_map[str(article["id"])] = article["updated_at"]

                    # Track last file date
                    updated_at = article.get("updated_at")
                    if updated_at:
                        try:
                            article_date = datetime.fromisoformat(
                                updated_at.replace("Z", "+00:00")
                            )
                            if not last_file_date or article_date > last_file_date:
                                last_file_date = article_date
                        except Exception:
                            pass

                except Exception as e:
                    error_msg = f"Error updating article {article.get('id')}: {str(e)}"
                    logger.error(error_msg)
                    kb_errors.append(error_msg)
                    continue

            # Update last synced time and persist article updated_at map (skip unchanged next run)
            logger.info(f"Updating knowledge base {kb.id} last synced time...")
            kb_update = _kb_update_dict(kb)
            kb_update["last_synced"] = datetime.now()
            kb_update["last_sync_status"] = (
                "success_with_warnings" if kb_errors else "success"
            )
            kb_update["last_sync_error"] = (
                "; ".join(kb_errors[:5]) if kb_errors else ""
            )
            if last_file_date:
                kb_update["last_file_date"] = last_file_date
            extra = dict(kb_update.get("extra_metadata") or {})
            extra[article_updated_at_key] = article_updated_at_map
            kb_update["extra_metadata"] = extra
            await kb_service.update(kb.id, KBCreate(**kb_update))

            articles_added_tot += articles_added
            articles_deleted_tot += articles_deleted
            articles_updated_tot += articles_updated
            processed_ds += 1
            entry: dict[str, Any] = {
                "kb_id": str(kb.id),
                "name": kb.name,
                "status": kb_update["last_sync_status"],
                "articles_added": articles_added,
                "articles_updated": articles_updated,
                "articles_deleted": articles_deleted,
            }
            if kb_errors:
                entry["warnings"] = kb_errors[:10]
            per_kb.append(entry)

        except Exception as e:
            error_msg = f"Error processing SalesForce datasource {ds.name}: {str(e)}"
            logger.error(error_msg)
            # Update KB with error status
            kb_update = _kb_update_dict(kb)
            kb_update["last_synced"] = datetime.now()
            kb_update["last_sync_status"] = "error"
            kb_update["last_sync_error"] = str(e)
            await kb_service.update(kb.id, KBCreate(**kb_update))
            per_kb.append(
                {
                    "kb_id": str(kb.id),
                    "name": kb.name,
                    "status": "error",
                    "error": str(e),
                }
            )
            continue

    res = {
        "status": "completed",
        "articles_added": articles_added_tot,
        "articles_deleted": articles_deleted_tot,
        "articles_updated": articles_updated_tot,
        "datasources_processed": processed_ds,
        "per_kb": per_kb,
    }

    logger.info(f"SalesForce article import completed with result: {res}")
    return res
