import copy
import logging
from datetime import datetime
from typing import Any, List, Optional
from urllib.parse import urlparse
from uuid import UUID

from bs4 import BeautifulSoup
from celery import shared_task
from croniter import croniter
from sqlalchemy import select

from app.core.observability.datadog_observability import datadog_observability
from app.core.utils.encryption_utils import decrypt_key
from app.core.utils.html_utils import html2markdown, html2plaintext
from app.db.models.knowledge_base import KnowledgeBaseModel
from app.db.transaction_manager import TransactionManager
from app.dependencies.injector import injector
from app.modules.data.load_result import article_sync_outcome, load_document, sync_result_fields
from app.modules.data.manager import AgentRAGServiceManager
from app.modules.integration.salesforce import SalesforceConnector
from app.schemas.agent_knowledge import KBRead
from app.schemas.dynamic_form_schemas import AGENT_RAG_FORM_SCHEMAS_DICT
from app.schemas.dynamic_form_schemas.app_settings_schemas import (
    get_encrypted_fields_for_type,
)
from app.services.agent_knowledge import KnowledgeBaseService
from app.services.app_settings import AppSettingsService
from app.services.datasources import DataSourceService

logger = logging.getLogger(__name__)


CONTENT_FORMATS = ("text", "markdown", "html")
ARTICLE_UPDATED_AT_KEY = "salesforce_article_updated_at"
FULL_LINK_SCHEMES = ("http", "https", "mailto", "tel")
PROGRESS_SAVE_EVERY = 50
SETTINGS_CHANGED_WARNING = (
    "The format or RAG settings changed during this sync. The next sync copies every article again."
)


def _resolve_content_format(extra_metadata: dict) -> str:
    """Return the KB's content format; the legacy ``allow_html_content`` flag maps to html."""
    content_format = extra_metadata.get("content_format")
    if content_format in CONTENT_FORMATS:
        return content_format
    if extra_metadata.get("allow_html_content"):
        return "html"
    return "text"


def _is_full_link(href: str) -> bool:
    return urlparse(href).scheme in FULL_LINK_SCHEMES or href.startswith("//")


def _keep_only_full_links(html: str) -> str:
    """Relative links lead nowhere outside SalesForce, so only their text is kept."""
    soup = BeautifulSoup(html, "html.parser")
    changed = False
    for link in soup.find_all("a", href=True):
        if not _is_full_link(link["href"].strip()):
            link.unwrap()
            changed = True
    return str(soup) if changed else html


def _parse_article_body(body: Optional[str], content_format: str) -> str:
    """Convert an article's HTML body to the KB's content format."""
    if not body:
        return ""
    if content_format == "html":
        return _keep_only_full_links(body)
    if content_format == "markdown":
        return html2markdown(_keep_only_full_links(body))
    return html2plaintext(body)


def _fill_field_default(values: dict, field: dict) -> None:
    if "default" in field and field["name"] not in values:
        values[field["name"]] = field["default"]


def _controlling_field(section: dict) -> Optional[dict]:
    conditional_fields = section.get("conditional_fields") or {}
    for field in section["fields"]:
        option_values = {option["value"] for option in field.get("options") or []}
        if option_values & conditional_fields.keys():
            return field
    return None


def _fill_section_defaults(values: dict, section: dict) -> None:
    for field in section["fields"]:
        _fill_field_default(values, field)
    controlling_field = _controlling_field(section)
    if controlling_field is None:
        return
    control_value = values.get(controlling_field["name"]) or controlling_field.get("default")
    for field in section["conditional_fields"].get(control_value, []):
        _fill_field_default(values, field)


def _with_rag_editor_defaults(rag_config: Optional[dict]) -> dict:
    """Fill only the values the RAG editor adds when missing; values already set are never changed, so real changes stay visible."""
    config = copy.deepcopy(rag_config or {})
    for rag_type, type_schema in AGENT_RAG_FORM_SCHEMAS_DICT.items():
        if config.get(rag_type) is None:
            config[rag_type] = {}
        values = config[rag_type]
        if not isinstance(values, dict):
            continue
        values.setdefault("enabled", rag_type == "vector")
        for section in type_schema["sections"]:
            _fill_section_defaults(values, section)
    return config


def _copy_settings(kb: Any) -> tuple[str, dict]:
    """The settings an article copy depends on, compared the same way on save and at the end of a sync."""
    return _resolve_content_format(kb.extra_metadata or {}), _with_rag_editor_defaults(kb.rag_config)


def clear_copy_dates_on_content_change(current: Any, incoming: Any) -> None:
    """On save, keep the stored copy dates; clear them when the format or RAG settings change, so the next sync re-copies every article."""
    if incoming.type != "salesforce":
        return
    current_metadata = current.extra_metadata or {}
    incoming_metadata = dict(incoming.extra_metadata or {})
    format_changed = _resolve_content_format(current_metadata) != _resolve_content_format(incoming_metadata)
    rag_config_changed = incoming.rag_config is not None and (
        _with_rag_editor_defaults(current.rag_config) != _with_rag_editor_defaults(incoming.rag_config)
    )
    stored_copy_dates = current_metadata.get(ARTICLE_UPDATED_AT_KEY)
    if format_changed or rag_config_changed:
        incoming_metadata[ARTICLE_UPDATED_AT_KEY] = {}
    elif stored_copy_dates is None:
        incoming_metadata.pop(ARTICLE_UPDATED_AT_KEY, None)
    else:
        incoming_metadata[ARTICLE_UPDATED_AT_KEY] = stored_copy_dates
    incoming.extra_metadata = incoming_metadata


async def apply_stored_copy_dates_on_save(kb_service: KnowledgeBaseService, kb_id: UUID, incoming: Any) -> None:
    """Lock the KB row while a save reads its copy dates, so a running sync cannot write between the read and the save."""
    if incoming.type != "salesforce":
        return
    current_row = await _current_kb_row(kb_service, kb_id)
    if current_row is not None:
        clear_copy_dates_on_content_change(current_row, incoming)


def _sync_fields(status: str, error: str = "") -> dict[str, Any]:
    return sync_result_fields(status, error)


def _with_settings_warning(fields: dict[str, Any]) -> dict[str, Any]:
    error = fields.get("last_sync_error") or ""
    nothing_copied = fields.get("last_sync_status") == "error"
    return {
        **fields,
        "last_sync_status": "error" if nothing_copied else "success_with_warnings",
        "last_sync_error": f"{SETTINGS_CHANGED_WARNING}; {error}" if error else SETTINGS_CHANGED_WARNING,
    }


async def _current_kb_row(
    kb_service: KnowledgeBaseService, kb_id: UUID, lock: bool = True
) -> Optional[KnowledgeBaseModel]:
    """Re-read the KB row (locked for a write), so the sync sees changes saved since it started."""
    stmt = select(KnowledgeBaseModel).where(KnowledgeBaseModel.id == kb_id).execution_options(populate_existing=True)
    if lock:
        stmt = stmt.with_for_update(key_share=True)
    result = await kb_service.repository.db.execute(stmt)
    return result.scalars().first()


async def _kb_as_it_is_now(kb_service: KnowledgeBaseService, kb_id: UUID) -> Optional[KBRead]:
    """Read the KB when its turn comes, so a scheduled run uses the settings saved since the run started."""
    row = await _current_kb_row(kb_service, kb_id, lock=False)
    return KBRead.model_validate(row, from_attributes=True) if row is not None else None


async def _save_sync_result(
    kb_service: KnowledgeBaseService,
    started_kb: Any,
    fields: dict[str, Any],
    copy_dates: Optional[dict] = None,
) -> dict[str, Any]:
    """Write only the sync's own fields onto the current KB row and commit, so the row is not held for later KBs."""
    row = await _current_kb_row(kb_service, started_kb.id)
    if row is None:
        logger.warning(f"Knowledge base {started_kb.id} was deleted during the sync; its result is not saved")
    else:
        fields = await _write_sync_fields(kb_service, row, started_kb, fields, copy_dates)
    await injector.get(TransactionManager).commit()
    return fields


async def _write_sync_fields(
    kb_service: KnowledgeBaseService,
    row: KnowledgeBaseModel,
    started_kb: Any,
    fields: dict[str, Any],
    copy_dates: Optional[dict],
) -> dict[str, Any]:
    if copy_dates is not None:
        if _settings_unchanged(row, started_kb):
            _set_copy_dates(row, copy_dates)
        else:
            fields = _with_settings_warning(fields)
    for name, value in fields.items():
        setattr(row, name, value)
    await kb_service.repository.update(row)
    return fields


def _settings_unchanged(row: KnowledgeBaseModel, started_kb: Any) -> bool:
    return _copy_settings(row) == _copy_settings(started_kb)


def _set_copy_dates(row: KnowledgeBaseModel, copy_dates: dict) -> None:
    row.extra_metadata = {**(row.extra_metadata or {}), ARTICLE_UPDATED_AT_KEY: dict(copy_dates)}


async def _save_progress(kb_service: KnowledgeBaseService, started_kb: Any, copy_dates: dict) -> None:
    """Save only the copy dates so far, so a sync cut off by the time limit continues where it stopped."""
    row = await _current_kb_row(kb_service, started_kb.id)
    if row is not None and _settings_unchanged(row, started_kb):
        _set_copy_dates(row, copy_dates)
        await kb_service.repository.update(row)
    await injector.get(TransactionManager).commit()


class _ProgressSaver:
    """Saves the copy dates after every PROGRESS_SAVE_EVERY copied articles."""

    def __init__(self, kb_service: KnowledgeBaseService, started_kb: Any, copy_dates: dict):
        self._kb_service = kb_service
        self._started_kb = started_kb
        self._copy_dates = copy_dates
        self._copied_since_save = 0

    async def before_next_article(self) -> None:
        if self._copied_since_save >= PROGRESS_SAVE_EVERY:
            await _save_progress(self._kb_service, self._started_kb, self._copy_dates)
            self._copied_since_save = 0
        self._copied_since_save += 1


def _select_articles(articles: List[dict], include_restricted: bool) -> List[dict]:
    """Keep only public articles unless restricted ones are explicitly included."""
    if include_restricted:
        return list(articles)
    return [article for article in articles if article.get("is_public")]


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

    result = run_async_in_celery(
        import_salesforce_articles_to_kb_async_with_scope(kb_id=kb_id, sync_now=sync_now),
        timeout=15 * 60,
        task_name="import_salesforce_articles_to_kb",
    )
    datadog_observability.tag_kb_sync("salesforce", result)
    return result


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
        logger.debug(f"Results: {result.get('per_kb')}")
    return result


async def import_salesforce_articles_to_kb_async(
    kb_id: Optional[UUID] = None, sync_now: bool = False
):
    """Async implementation of SalesForce Knowledge article import.

    Persists ``last_synced``, ``last_sync_status``, and ``last_sync_error`` on the KB row so
    the UI can show outcome, and ``last_successful_sync`` when the sync succeeded.
    Returns aggregate counts plus ``per_kb`` for API responses.
    Only these sync fields and the copy dates are written, so changes saved during a sync are kept.
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
    kbs_failed = 0
    articles_added_tot = 0
    articles_deleted_tot = 0
    articles_updated_tot = 0
    last_file_date = None

    for listed_kb in kbList:
        kb = await _kb_as_it_is_now(kb_service, listed_kb.id)
        if kb is None:
            per_kb.append(
                {"kb_id": str(listed_kb.id), "name": listed_kb.name, "status": "skipped", "reason": "not_found"}
            )
            continue
        logger.debug(f"Processing knowledge base {kb.name}")
        # Reset per-KB so one KB's newest article date can't leak onto another KB in a
        # multi-KB (scheduled) run.
        last_file_date = None

        if not sync_now and (kb.sync_active == 0 or not kb.sync_source_id):
            logger.debug(
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
            logger.debug(f"Knowledge base {kb.id} has no sync source")
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
            logger.debug(
                f"Knowledge base {kb.id} has a sync source that is not SalesForce ({ds.source_type})"
            )
            if sync_now or kb_id is not None:
                await _save_sync_result(
                    kb_service,
                    kb,
                    _sync_fields("error", f"Sync source is not SalesForce (type={ds.source_type})"),
                )
                kbs_failed += 1
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
            logger.debug(f"Knowledge base {kb.id} has no sync schedule")
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
                logger.debug("Getting next run time from last synced")
                next_run_time = cron_iter.get_next(start_time=kb.last_synced)
                next_run_time = datetime.fromtimestamp(next_run_time)
                logger.debug(
                    f"Knowledge base {kb.id} last synced at {kb.last_synced}, next run time: {next_run_time}"
                )

            if datetime.now() < next_run_time:
                logger.debug(
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
            logger.debug(
                f"Knowledge base {kb.id} has no connection data for sync source {ds.name}"
            )
            if sync_now or kb_id is not None:
                await _save_sync_result(
                    kb_service, kb, _sync_fields("error", "SalesForce datasource has no connection data")
                )
                kbs_failed += 1
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
            await _save_sync_result(kb_service, kb, _sync_fields("error", err))
            kbs_failed += 1
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

            extra_metadata = kb.extra_metadata or {}
            include_restricted = bool(extra_metadata.get("include_restricted_articles"))
            fetched_articles = await salesforce_connector.fetch_knowledge_articles(
                content_field=content_field,
                language=language,
                data_category=data_category,
                read_public_flag=not include_restricted,
            )

            content_format = _resolve_content_format(extra_metadata)
            articles = _select_articles(fetched_articles, include_restricted)
            skipped_restricted = len(fetched_articles) - len(articles)
            if skipped_restricted:
                logger.debug(
                    f"Skipping {skipped_restricted} non-public articles for knowledge base {kb.id}"
                )

            if not fetched_articles:
                logger.debug(
                    f"No articles found in SalesForce for datasource {ds.name}"
                )
                processed_ds += 1
                await _save_sync_result(kb_service, kb, _sync_fields("success"))
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

            logger.debug("Getting existing articles from RAG...")
            existing_articles = await rag_manager.get_document_ids(kb)
            logger.debug(
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
            logger.debug(
                f"Found {len(new_articles)} new articles to process for knowledge base {kb.id}"
            )

            # Find deleted articles (exist in RAG but not in SalesForce)
            deleted_article_ids = [
                article_id
                for article_id in existing_articles
                if article_id.startswith(f"KB:{str(kb.id)}#article_")
                and article_id not in salesforce_article_ids
            ]
            logger.debug(
                f"Found {len(deleted_article_ids)} deleted articles to remove for knowledge base {kb.id}"
            )

            # Load last-known updated_at per article from KB extra_metadata (skip-if-unchanged)
            article_updated_at_key = ARTICLE_UPDATED_AT_KEY
            stored_updated_at: dict = extra_metadata.get(article_updated_at_key) or {}
            # Work on a copy so we can persist it after add/update/delete
            article_updated_at_map = dict(stored_updated_at)
            progress = _ProgressSaver(kb_service, kb, article_updated_at_map)

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
                logger.debug(
                    f"Skipping {skipped_unchanged} existing articles (unchanged) for knowledge base {kb.id}"
                )

            # Delete removed articles from RAG and from our updated_at map
            article_id_prefix = f"KB:{str(kb.id)}#article_"
            if deleted_article_ids:
                for doc_id in deleted_article_ids:
                    try:
                        logger.debug(f"Deleting article {doc_id} from RAG...")
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
                article_body = _parse_article_body(article.get("body"), content_format)
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
                await progress.before_next_article()
                try:
                    article_id = f"KB:{str(kb.id)}#article_{article['id']}"
                    content, metadata = _build_content_and_metadata(article)

                    warning = await load_document(rag_manager, kb, article_id, content, metadata, metadata["name"])
                    if warning:
                        kb_errors.append(warning)
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
                    article_updated_at_map.pop(str(article.get("id")), None)
                    continue

            # Update existing articles
            for article in updated_articles:
                await progress.before_next_article()
                try:
                    article_id = f"KB:{str(kb.id)}#article_{article['id']}"
                    content, metadata = _build_content_and_metadata(article)

                    # Delete and re-add to update
                    await rag_manager.delete_document(kb, article_id)
                    warning = await load_document(rag_manager, kb, article_id, content, metadata, metadata["name"])
                    if warning:
                        kb_errors.append(warning)
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
                    article_updated_at_map.pop(str(article.get("id")), None)
                    continue

            # Update last synced time and persist article updated_at map (skip unchanged next run)
            logger.debug(f"Updating knowledge base {kb.id} last synced time...")
            sync_status, sync_message = article_sync_outcome(
                len(new_articles) + len(updated_articles),
                articles_added + articles_updated,
                kb_errors,
                had_articles=bool(existing_articles),
            )
            final_fields = _sync_fields(sync_status, sync_message)
            if last_file_date:
                final_fields["last_file_date"] = last_file_date
            saved_fields = await _save_sync_result(
                kb_service, kb, final_fields, copy_dates=article_updated_at_map
            )
            if saved_fields["last_sync_status"] == "error":
                kbs_failed += 1

            articles_added_tot += articles_added
            articles_deleted_tot += articles_deleted
            articles_updated_tot += articles_updated
            processed_ds += 1
            entry: dict[str, Any] = {
                "kb_id": str(kb.id),
                "name": kb.name,
                "status": saved_fields["last_sync_status"],
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
            await injector.get(TransactionManager).rollback()
            await _save_sync_result(kb_service, kb, _sync_fields("error", str(e)))
            kbs_failed += 1
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
        "kbs_failed": kbs_failed,
        "per_kb": per_kb,
    }

    logger.info(
        "SalesForce article import completed: "
        f"{articles_added_tot} added, {articles_updated_tot} updated, "
        f"{articles_deleted_tot} deleted across {processed_ds} datasource(s)"
    )
    return res
