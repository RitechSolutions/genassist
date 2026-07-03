"""Unit tests for the SalesForce Knowledge article sync task.

The SalesforceConnector, AppSettingsService, KnowledgeBaseService, DataSourceService and
AgentRAGServiceManager are all faked, so no live DB / Redis / network / SalesForce is
required. Covers add on first sync, incremental update-only-edited via
``salesforce_article_updated_at``, delete of removed articles, error status on connector
failure, no-articles success, and dispatch-by-type through ``batch_process_files_kb_async``
(FR-3/4/5/6/9/10, AC-4/8/9).
"""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schemas.agent_knowledge import KBRead
from app.services.agent_knowledge import KnowledgeBaseService
from app.services.app_settings import AppSettingsService
from app.services.datasources import DataSourceService

TASK_MODULE = "app.tasks.salesforce_article_sync_tasks"

_APP_SETTINGS_ID = str(uuid.uuid4())


def _make_kb(kb_id, extra_metadata=None):
    return KBRead(
        id=kb_id,
        name="SF KB",
        type="salesforce",
        sync_active=True,
        sync_source_id=uuid.uuid4(),
        extra_metadata=extra_metadata or {},
    )


def _make_datasource():
    return SimpleNamespace(
        name="SF DS",
        source_type="salesforce",
        connection_data={
            "app_settings_id": _APP_SETTINGS_ID,
            "content_field": "Body__c",
        },
    )


def _make_app_settings_service():
    service = MagicMock()
    app_settings = SimpleNamespace(
        type="Salesforce",
        values={
            "salesforce_instance_url": "https://myorg.my.salesforce.com",
            "salesforce_client_id": "client-id",
            "salesforce_client_secret": "secret-plain",
        },
    )
    service.get_by_id = AsyncMock(return_value=app_settings)
    return service


class _FakeRagManager:
    """Records add/delete operations against an in-memory doc-id store."""

    def __init__(self, existing_ids=None):
        self.existing = list(existing_ids or [])
        self.added = []
        self.deleted = []

    async def get_document_ids(self, kb):
        return list(self.existing)

    async def add_document(self, kb, doc_id, content, metadata):
        self.added.append((doc_id, content, metadata))
        return {"ok": True}

    async def delete_document(self, kb, doc_id):
        self.deleted.append(doc_id)
        return {"ok": True}


def _patch_env(kb, datasource, rag_manager, kb_service, app_settings_service):
    """Patch the task module's injector so injector.get(...) returns the fakes."""
    ds_service = MagicMock()
    ds_service.get_by_id = AsyncMock(return_value=datasource)

    fake_injector = MagicMock()

    def _get(dependency):
        if dependency is KnowledgeBaseService:
            return kb_service
        if dependency is DataSourceService:
            return ds_service
        if dependency is AppSettingsService:
            return app_settings_service
        # AgentRAGServiceManager
        return rag_manager

    fake_injector.get.side_effect = _get
    return patch(f"{TASK_MODULE}.injector", fake_injector)


def _make_kb_service(kb):
    service = MagicMock()
    service.get_by_id = AsyncMock(return_value=kb)
    service.update = AsyncMock(return_value=kb)
    return service


def _patch_connector(articles=None, raise_exc=None):
    connector_instance = MagicMock()
    if raise_exc is not None:
        connector_instance.fetch_knowledge_articles = AsyncMock(side_effect=raise_exc)
    else:
        connector_instance.fetch_knowledge_articles = AsyncMock(return_value=articles or [])
    return (
        patch(f"{TASK_MODULE}.SalesforceConnector", return_value=connector_instance),
        connector_instance,
    )


async def _run_sync(kb, datasource, rag_manager, articles=None, raise_exc=None):
    from app.tasks.salesforce_article_sync_tasks import (
        import_salesforce_articles_to_kb_async,
    )

    kb_service = _make_kb_service(kb)
    app_settings_service = _make_app_settings_service()
    connector_patch, _ = _patch_connector(articles=articles, raise_exc=raise_exc)
    with _patch_env(kb, datasource, rag_manager, kb_service, app_settings_service), connector_patch:
        result = await import_salesforce_articles_to_kb_async(kb_id=kb.id, sync_now=True)
    return result, kb_service


@pytest.mark.asyncio
async def test_first_sync_adds_all_articles():
    """FR-3: first sync ingests every in-scope article."""
    kb_id = uuid.uuid4()
    kb = _make_kb(kb_id)
    rag = _FakeRagManager(existing_ids=[])
    articles = [
        {"id": "ka-1", "title": "T1", "summary": "S1", "body": "<p>B1</p>", "updated_at": "2026-01-01T00:00:00Z"},
        {"id": "ka-2", "title": "T2", "summary": "", "body": "B2", "updated_at": "2026-01-02T00:00:00Z"},
    ]

    result, kb_service = await _run_sync(kb, _make_datasource(), rag, articles=articles)

    assert result["articles_added"] == 2
    assert result["articles_updated"] == 0
    assert result["articles_deleted"] == 0
    added_ids = {doc_id for doc_id, _, _ in rag.added}
    assert added_ids == {f"KB:{kb_id}#article_ka-1", f"KB:{kb_id}#article_ka-2"}
    # HTML stripped by default; title + summary + body composed
    contents = {doc_id: content for doc_id, content, _ in rag.added}
    assert "<p>" not in contents[f"KB:{kb_id}#article_ka-1"]
    assert "B1" in contents[f"KB:{kb_id}#article_ka-1"]

    # status persisted as success with cleared error, updated_at map tracked
    update_kb = kb_service.update.await_args.args[1]
    assert update_kb.last_sync_status == "success"
    assert update_kb.last_sync_error == ""
    tracked = update_kb.extra_metadata["salesforce_article_updated_at"]
    assert tracked == {"ka-1": "2026-01-01T00:00:00Z", "ka-2": "2026-01-02T00:00:00Z"}


@pytest.mark.asyncio
async def test_incremental_updates_only_edited_articles():
    """FR-6/AC-4: only the article whose LastPublishedDate advanced is re-indexed."""
    kb_id = uuid.uuid4()
    existing = [f"KB:{kb_id}#article_ka-1", f"KB:{kb_id}#article_ka-2"]
    kb = _make_kb(
        kb_id,
        extra_metadata={
            "salesforce_article_updated_at": {
                "ka-1": "2026-01-01T00:00:00Z",
                "ka-2": "2026-01-02T00:00:00Z",
            }
        },
    )
    rag = _FakeRagManager(existing_ids=list(existing))
    articles = [
        # ka-1 unchanged, ka-2 edited (newer timestamp)
        {"id": "ka-1", "title": "T1", "summary": "", "body": "B1", "updated_at": "2026-01-01T00:00:00Z"},
        {"id": "ka-2", "title": "T2", "summary": "", "body": "B2 edited", "updated_at": "2026-01-05T00:00:00Z"},
    ]

    result, _ = await _run_sync(kb, _make_datasource(), rag, articles=articles)

    assert result["articles_added"] == 0
    assert result["articles_updated"] == 1
    assert result["articles_deleted"] == 0
    # update = delete then re-add for ka-2 only
    assert rag.deleted == [f"KB:{kb_id}#article_ka-2"]
    assert [doc_id for doc_id, _, _ in rag.added] == [f"KB:{kb_id}#article_ka-2"]


@pytest.mark.asyncio
async def test_removed_articles_are_deleted():
    """FR-6/AC-4: docs in RAG no longer returned by SalesForce are removed."""
    kb_id = uuid.uuid4()
    existing = [f"KB:{kb_id}#article_ka-1", f"KB:{kb_id}#article_ka-old"]
    kb = _make_kb(
        kb_id,
        extra_metadata={
            "salesforce_article_updated_at": {
                "ka-1": "2026-01-01T00:00:00Z",
                "ka-old": "2025-01-01T00:00:00Z",
            }
        },
    )
    rag = _FakeRagManager(existing_ids=list(existing))
    articles = [
        {"id": "ka-1", "title": "T1", "summary": "", "body": "B1", "updated_at": "2026-01-01T00:00:00Z"},
    ]

    result, kb_service = await _run_sync(kb, _make_datasource(), rag, articles=articles)

    assert result["articles_deleted"] == 1
    assert rag.deleted == [f"KB:{kb_id}#article_ka-old"]
    # the removed article is dropped from the tracked updated_at map
    tracked = kb_service.update.await_args.args[1].extra_metadata["salesforce_article_updated_at"]
    assert "ka-old" not in tracked


@pytest.mark.asyncio
async def test_connector_failure_records_error_status():
    """FR-10/AC-8: a connector failure records an error status and does not crash."""
    kb_id = uuid.uuid4()
    kb = _make_kb(kb_id)
    rag = _FakeRagManager(existing_ids=[])

    result, kb_service = await _run_sync(
        kb, _make_datasource(), rag, raise_exc=RuntimeError("invalid_client")
    )

    per_kb = result["per_kb"][0]
    assert per_kb["status"] == "error"
    update_kb = kb_service.update.await_args.args[1]
    assert update_kb.last_sync_status == "error"
    assert "invalid_client" in update_kb.last_sync_error
    # nothing added/deleted on failure
    assert rag.added == []
    assert rag.deleted == []


@pytest.mark.asyncio
async def test_no_articles_is_success_with_cleared_error():
    """FR-10: an empty result set is a clean success with zero counts and no error."""
    kb_id = uuid.uuid4()
    kb = _make_kb(kb_id, extra_metadata={})
    rag = _FakeRagManager(existing_ids=[])

    result, kb_service = await _run_sync(kb, _make_datasource(), rag, articles=[])

    assert result["articles_added"] == 0
    assert result["articles_updated"] == 0
    assert result["articles_deleted"] == 0
    update_kb = kb_service.update.await_args.args[1]
    assert update_kb.last_sync_status == "success"
    assert update_kb.last_sync_error == ""


@pytest.mark.asyncio
async def test_empty_fetch_does_not_delete_existing_docs():
    """FR-10/AC-8: an empty result set must NOT wipe already-indexed KB documents."""
    kb_id = uuid.uuid4()
    kb = _make_kb(kb_id, extra_metadata={})
    rag = _FakeRagManager(existing_ids=[f"KB:{kb_id}#article_ka-old"])

    result, kb_service = await _run_sync(kb, _make_datasource(), rag, articles=[])

    # No deletions performed despite an existing doc and a zero-article fetch.
    assert rag.deleted == []
    assert result["articles_deleted"] == 0
    update_kb = kb_service.update.await_args.args[1]
    assert update_kb.last_sync_status == "success"


@pytest.mark.asyncio
async def test_fetch_exception_preserves_existing_docs():
    """FR-10: a fetch failure records an error and performs no RAG deletions."""
    kb_id = uuid.uuid4()
    kb = _make_kb(kb_id, extra_metadata={})
    rag = _FakeRagManager(existing_ids=[f"KB:{kb_id}#article_ka-old"])

    result, kb_service = await _run_sync(
        kb, _make_datasource(), rag, raise_exc=RuntimeError("boom")
    )

    assert rag.deleted == []
    assert rag.added == []
    update_kb = kb_service.update.await_args.args[1]
    assert update_kb.last_sync_status == "error"


@pytest.mark.asyncio
async def test_batch_dispatch_routes_salesforce_kb_to_importer():
    """FR-8/AC-9: batch_process_files_kb_async routes a salesforce KB to the SF importer."""
    kb_id = uuid.uuid4()
    kb = _make_kb(kb_id)

    kb_service = MagicMock()
    kb_service.get_by_id = AsyncMock(return_value=kb)

    fake_injector = MagicMock()

    def _get(dependency):
        if dependency is KnowledgeBaseService:
            return kb_service
        return MagicMock()

    fake_injector.get.side_effect = _get

    from app.tasks import kb_batch_tasks

    sf_result = {"status": "completed", "articles_added": 3}
    with (
        patch.object(kb_batch_tasks, "injector", fake_injector),
        patch.object(
            kb_batch_tasks,
            "import_salesforce_articles_to_kb_async",
            new=AsyncMock(return_value=sf_result),
        ) as sf_import,
        patch.object(
            kb_batch_tasks,
            "import_zendesk_articles_to_kb_async",
            new=AsyncMock(return_value={}),
        ) as zd_import,
    ):
        result = await kb_batch_tasks.batch_process_files_kb_async(kb_id=str(kb_id))

    sf_import.assert_awaited_once_with(kb_id=kb.id, sync_now=True)
    zd_import.assert_not_awaited()
    assert result["salesforce_sync_results"] == [
        {"kb_id": str(kb_id), "type": "salesforce", "result": sf_result}
    ]
    assert result["salesforce_kbs_synced"] == 1
