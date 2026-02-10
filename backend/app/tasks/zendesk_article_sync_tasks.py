import asyncio
import json
import logging
from datetime import datetime
from typing import Optional
from uuid import UUID
from croniter import croniter

from app.dependencies.injector import injector
from app.modules.data.manager import AgentRAGServiceManager
from app.modules.integration.zendesk import ZendeskConnector
from app.schemas.agent_knowledge import KBCreate
from app.services.agent_knowledge import KnowledgeBaseService
from app.services.datasources import DataSourceService
from celery import shared_task


logger = logging.getLogger(__name__)


@shared_task
def import_zendesk_articles_to_kb():
    """
    Import articles from Zendesk Help Center into the knowledge base.
    """
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    if loop.is_closed():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    return loop.run_until_complete(import_zendesk_articles_to_kb_async_with_scope())


async def import_zendesk_articles_to_kb_async_with_scope():
    """Wrapper to run Zendesk article import for all tenants"""
    from app.tasks.base import run_task_with_tenant_support
    result = await run_task_with_tenant_support(
        import_zendesk_articles_to_kb_async,
        "Zendesk article import"
    )
    if result.get("status") == "success":
        logger.info(f"Results: {result.get('results')}")
    return result


async def import_zendesk_articles_to_kb_async(kb_id: Optional[UUID] = None):
    """Async implementation of Zendesk article import"""
    logger.info("Starting Zendesk article import...")

    kb_service = injector.get(KnowledgeBaseService)
    rag_manager = injector.get(AgentRAGServiceManager)

    kbList = []
    if not kb_id:
        kbList = await kb_service.get_all()
    else:
        kbList = [await kb_service.get_by_id(kb_id)]

    processed_ds = 0
    articles_added_tot = 0
    articles_deleted_tot = 0
    articles_updated_tot = 0
    last_file_date = None

    for kb in kbList:
        logger.info(f"Processing knowledge base {kb.name}")

        if kb.sync_active == 0 or not kb.sync_source_id:
            logger.info(
                f"Knowledge base {kb.id} is not active or does not have a sync source"
            )
            continue

        ds = await injector.get(DataSourceService).get_by_id(kb.sync_source_id, True)
        if not ds:
            logger.info(f"Knowledge base {kb.id} has no sync source")
            continue

        if ds.source_type.lower() != "zendesk":
            logger.info(
                f"Knowledge base {kb.id} has a sync source that is not Zendesk ({ds.source_type})"
            )
            continue

        cron_string = kb.sync_schedule
        if not cron_string:
            logger.info(f"Knowledge base {kb.id} has no sync schedule")
            continue

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
            continue

        if not ds.connection_data:
            logger.info(
                f"Knowledge base {kb.id} has no connection data for sync source {ds.name}"
            )
            continue

        conn_data = ds.connection_data

        subdomain = conn_data.get("subdomain")
        email = conn_data.get("email")
        api_token = conn_data.get("api_token")
        locale = conn_data.get("locale")  # Optional
        section_id = conn_data.get("section_id")  # Optional

        if not subdomain or not email or not api_token:
            logger.error(
                f"Knowledge base {kb.id} has incomplete Zendesk connection data"
            )
            continue

        try:
            # Fetch articles from Zendesk using ZendeskConnector
            zendesk_connector = ZendeskConnector(
                subdomain=subdomain, email=email, api_token=api_token
            )
            articles = await zendesk_connector.fetch_articles(
                locale=locale, section_id=section_id
            )

            if not articles:
                logger.info(
                    f"No articles found in Zendesk for datasource {ds.name}"
                )
                processed_ds += 1
                kb.last_synced = datetime.now()
                await kb_service.update(kb.id, KBCreate(**kb.__dict__))  # type: ignore
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

            # Create a set of article IDs from Zendesk
            zendesk_article_ids = {
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

            # Find deleted articles (exist in RAG but not in Zendesk)
            deleted_article_ids = [
                article_id
                for article_id in existing_articles
                if article_id.startswith(f"KB:{str(kb.id)}#article_")
                and article_id not in zendesk_article_ids
            ]
            logger.info(
                f"Found {len(deleted_article_ids)} deleted articles to remove for knowledge base {kb.id}"
            )

            # Load last-known updated_at per article from KB extra_metadata (for skip-if-unchanged)
            article_updated_at_key = "zendesk_article_updated_at"
            stored_updated_at: dict = (kb.extra_metadata or {}).get(
                article_updated_at_key
            ) or {}
            # Work on a copy so we can persist it after add/update/delete
            article_updated_at_map = dict(stored_updated_at)

            def _is_article_edited(article: dict) -> bool:
                """True if we have no stored updated_at or Zendesk's is newer."""
                aid = str(article["id"])
                zendesk_updated = article.get("updated_at") or ""
                if not zendesk_updated:
                    return True  # unknown freshness, treat as edited to be safe
                stored = stored_updated_at.get(aid)
                if not stored:
                    return True  # first time we've seen it in stored state
                # ISO8601 strings compare correctly as strings
                return zendesk_updated > stored

            # Find updated articles (exist in both AND edited in Zendesk since last sync)
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
                            zendesk_id = doc_id[len(article_id_prefix) :]
                            article_updated_at_map.pop(zendesk_id, None)
                    except Exception as e:
                        error_msg = f"Error deleting article {doc_id}: {str(e)}"
                        logger.error(error_msg)
                        kb_errors.append(error_msg)
                        continue

            # Add new articles to RAG
            for article in new_articles:
                try:
                    article_id = f"KB:{str(kb.id)}#article_{article['id']}"
                    article_title = article.get("title", "Untitled Article")
                    article_body = article.get("body", "")
                    article_url = article.get("html_url", "")

                    # Extract plain text from HTML body if needed
                    # For now, we'll use the body as-is (Zendesk API returns HTML)
                    content = f"{article_title}\n\n{article_body}"

                    metadata = {
                        "name": article_title,
                        "description": f"Zendesk article from {ds.name}",
                        "kb_id": str(kb.id),
                        "article_id": str(article["id"]),
                        "article_url": article_url,
                        "locale": article.get("locale", ""),
                        "section_id": str(article.get("section_id", "")),
                    }

                    res = await rag_manager.add_document(
                        kb, article_id, content, metadata
                    )
                    logger.info(f"Article {article_title} processed with result: {res}")
                    articles_added += 1
                    if article.get("updated_at"):
                        article_updated_at_map[str(article["id"])] = article[
                            "updated_at"
                        ]

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
                    article_title = article.get("title", "Untitled Article")
                    article_body = article.get("body", "")
                    article_url = article.get("html_url", "")

                    content = f"{article_title}\n\n{article_body}"

                    metadata = {
                        "name": article_title,
                        "description": f"Zendesk article from {ds.name}",
                        "kb_id": str(kb.id),
                        "article_id": str(article["id"]),
                        "article_url": article_url,
                        "locale": article.get("locale", ""),
                        "section_id": str(article.get("section_id", "")),
                    }

                    # Delete and re-add to update
                    await rag_manager.delete_document(kb, article_id)
                    res = await rag_manager.add_document(
                        kb, article_id, content, metadata
                    )
                    logger.info(f"Article {article_title} updated with result: {res}")
                    articles_updated += 1
                    if article.get("updated_at"):
                        article_updated_at_map[str(article["id"])] = article[
                            "updated_at"
                        ]

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
            kb_update = json.loads(kb.model_dump_json())
            kb_update["last_synced"] = datetime.now()
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

        except Exception as e:
            error_msg = f"Error processing Zendesk datasource {ds.name}: {str(e)}"
            logger.error(error_msg)
            # Update KB with error status
            kb_update = json.loads(kb.model_dump_json())
            kb_update["last_synced"] = datetime.now()
            kb_update["last_sync_status"] = "error"
            kb_update["last_sync_error"] = str(e)
            await kb_service.update(kb.id, KBCreate(**kb_update))
            continue

    res = {
        "status": "completed",
        "articles_added": articles_added_tot,
        "articles_deleted": articles_deleted_tot,
        "articles_updated": articles_updated_tot,
        "datasources_processed": processed_ds,
    }

    logger.info(f"Zendesk article import completed with result: {res}")
    return res
