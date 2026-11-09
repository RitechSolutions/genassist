"""Unit tests for the SalesForce Knowledge article sync task.

The SalesforceConnector, AppSettingsService, KnowledgeBaseService, DataSourceService and
AgentRAGServiceManager are all faked, so no live DB / Redis / network / SalesForce is
required. Covers add on first sync, incremental update-only-edited via
``salesforce_article_updated_at``, delete of removed articles, error status on connector
failure, no-articles success, and dispatch-by-type through ``batch_process_files_kb_async``
(FR-3/4/5/6/9/10, AC-4/8/9).
"""

import asyncio
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.db.transaction_manager import TransactionManager
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
        if dependency is TransactionManager:
            return kb_service.transactions
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


_SAME_AS_STARTED = object()


def _stored_row(kb, **changes):
    """The KB row as stored in the database when the sync writes its result."""
    row = SimpleNamespace(**kb.model_dump())
    row.extra_metadata = dict(kb.extra_metadata or {})
    for name, value in changes.items():
        setattr(row, name, value)
    return row


def _make_kb_service(kb, current_row=_SAME_AS_STARTED, row_at_start=None):
    """The KB row read when its turn starts (unlocked) and when its result is written (locked)."""
    start = row_at_start if row_at_start is not None else _stored_row(kb)
    row = _stored_row(kb) if current_row is _SAME_AS_STARTED else current_row

    async def _execute(stmt):
        lookup = MagicMock()
        lookup.scalars.return_value.first.return_value = row if stmt._for_update_arg is not None else start
        return lookup

    service = MagicMock()
    service.get_by_id = AsyncMock(return_value=kb)
    service.repository.db.execute = AsyncMock(side_effect=_execute)
    service.repository.update = AsyncMock(side_effect=lambda written: written)
    service.transactions.commit = AsyncMock()
    service.transactions.rollback = AsyncMock()
    return service


def _written_row(kb_service):
    return kb_service.repository.update.await_args.args[0]


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


async def _run_sync(kb, datasource, rag_manager, articles=None, raise_exc=None, current_row=_SAME_AS_STARTED):
    from app.tasks.salesforce_article_sync_tasks import (
        import_salesforce_articles_to_kb_async,
    )

    kb_service = _make_kb_service(kb, current_row)
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
        {"id": "ka-1", "title": "T1", "summary": "S1", "body": "<p>B1</p>", "updated_at": "2026-01-01T00:00:00Z", "is_public": True},
        {"id": "ka-2", "title": "T2", "summary": "", "body": "B2", "updated_at": "2026-01-02T00:00:00Z", "is_public": True},
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
    update_kb = _written_row(kb_service)
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
        extra_metadata={"salesforce_article_updated_at": {
                "ka-1": "2026-01-01T00:00:00Z",
                "ka-2": "2026-01-02T00:00:00Z",
            }},
    )
    rag = _FakeRagManager(existing_ids=list(existing))
    articles = [
        # ka-1 unchanged, ka-2 edited (newer timestamp)
        {"id": "ka-1", "title": "T1", "summary": "", "body": "B1", "updated_at": "2026-01-01T00:00:00Z", "is_public": True},
        {"id": "ka-2", "title": "T2", "summary": "", "body": "B2 edited", "updated_at": "2026-01-05T00:00:00Z", "is_public": True},
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
        extra_metadata={"salesforce_article_updated_at": {
                "ka-1": "2026-01-01T00:00:00Z",
                "ka-old": "2025-01-01T00:00:00Z",
            }},
    )
    rag = _FakeRagManager(existing_ids=list(existing))
    articles = [
        {"id": "ka-1", "title": "T1", "summary": "", "body": "B1", "updated_at": "2026-01-01T00:00:00Z", "is_public": True},
    ]

    result, kb_service = await _run_sync(kb, _make_datasource(), rag, articles=articles)

    assert result["articles_deleted"] == 1
    assert rag.deleted == [f"KB:{kb_id}#article_ka-old"]
    # the removed article is dropped from the tracked updated_at map
    tracked = _written_row(kb_service).extra_metadata["salesforce_article_updated_at"]
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
    update_kb = _written_row(kb_service)
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
    update_kb = _written_row(kb_service)
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
    update_kb = _written_row(kb_service)
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
    update_kb = _written_row(kb_service)
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


def _article(article_id, is_public=True, body="B", updated_at="2026-01-01T00:00:00Z"):
    return {
        "id": article_id,
        "title": f"T-{article_id}",
        "summary": "",
        "body": body,
        "updated_at": updated_at,
        "is_public": is_public,
    }


@pytest.mark.asyncio
async def test_non_public_articles_are_skipped_and_removed():
    kb_id = uuid.uuid4()
    kb = _make_kb(
        kb_id,
        extra_metadata={"salesforce_article_updated_at": {
                "ka-public": "2026-01-01T00:00:00Z",
                "ka-internal": "2026-01-01T00:00:00Z",
            }},
    )
    rag = _FakeRagManager(
        existing_ids=[f"KB:{kb_id}#article_ka-public", f"KB:{kb_id}#article_ka-internal"]
    )
    articles = [
        _article("ka-public"),
        _article("ka-internal", is_public=False),
        _article("ka-new-internal", is_public=False),
    ]

    result, kb_service = await _run_sync(kb, _make_datasource(), rag, articles=articles)

    assert rag.added == []
    assert rag.deleted == [f"KB:{kb_id}#article_ka-internal"]
    assert result["articles_deleted"] == 1
    tracked = _written_row(kb_service).extra_metadata["salesforce_article_updated_at"]
    assert set(tracked) == {"ka-public"}


@pytest.mark.asyncio
async def test_include_restricted_articles_copies_every_article():
    kb_id = uuid.uuid4()
    kb = _make_kb(kb_id, extra_metadata={"include_restricted_articles": True})
    rag = _FakeRagManager(existing_ids=[])
    articles = [_article("ka-public"), _article("ka-internal", is_public=False)]

    result, _ = await _run_sync(kb, _make_datasource(), rag, articles=articles)

    assert result["articles_added"] == 2
    added_ids = {doc_id for doc_id, _, _ in rag.added}
    assert added_ids == {f"KB:{kb_id}#article_ka-public", f"KB:{kb_id}#article_ka-internal"}


@pytest.mark.asyncio
async def test_all_restricted_fetch_still_removes_existing_docs():
    kb_id = uuid.uuid4()
    kb = _make_kb(kb_id, extra_metadata={})
    rag = _FakeRagManager(existing_ids=[f"KB:{kb_id}#article_ka-internal"])
    articles = [_article("ka-internal", is_public=False)]

    result, kb_service = await _run_sync(kb, _make_datasource(), rag, articles=articles)

    assert rag.deleted == [f"KB:{kb_id}#article_ka-internal"]
    assert result["articles_deleted"] == 1
    assert _written_row(kb_service).last_sync_status == "success"


@pytest.mark.asyncio
async def test_markdown_format_keeps_links():
    kb_id = uuid.uuid4()
    kb = _make_kb(kb_id, extra_metadata={"content_format": "markdown"})
    rag = _FakeRagManager(existing_ids=[])
    body = '<p>See <a href="https://example.com/docs">the docs</a> &amp; FAQ.</p>'

    await _run_sync(kb, _make_datasource(), rag, articles=[_article("ka-1", body=body)])

    content = rag.added[0][1]
    assert "[the docs](https://example.com/docs)" in content
    assert "&amp;" not in content


@pytest.mark.parametrize(
    "extra_metadata, expected",
    [
        ({}, "text"),
        ({"allow_html_content": True}, "html"),
        ({"allow_html_content": False}, "text"),
        ({"content_format": "markdown", "allow_html_content": True}, "markdown"),
        ({"content_format": "unknown"}, "text"),
    ],
)
def test_resolve_content_format(extra_metadata, expected):
    from app.tasks.salesforce_article_sync_tasks import _resolve_content_format

    assert _resolve_content_format(extra_metadata) == expected


@pytest.mark.parametrize(
    "body, content_format, expected",
    [
        (None, "text", ""),
        ("", "markdown", ""),
        ("<p>Fees &amp; charges</p>", "text", "Fees & charges"),
        ('<p><a href="https://example.com/a">Link</a></p>', "markdown", "[Link](https://example.com/a)"),
        ("<p>Raw &amp; kept</p>", "html", "<p>Raw &amp; kept</p>"),
    ],
)
def test_parse_article_body(body, content_format, expected):
    from app.tasks.salesforce_article_sync_tasks import _parse_article_body

    assert _parse_article_body(body, content_format) == expected


@pytest.mark.asyncio
@pytest.mark.parametrize("kb_type", ["salesforce", "zendesk"])
async def test_saving_sync_owned_kb_keeps_synced_articles(kb_type):
    from app.modules.data.manager import AgentRAGServiceManager

    manager = AgentRAGServiceManager()
    kb = KBRead(id=uuid.uuid4(), name="KB", type=kb_type, extra_metadata={})

    with patch.object(manager, "get_service", new=AsyncMock(return_value=None)) as get_service:
        await manager.load_knowledge_items([kb], action="update")

    get_service.assert_not_awaited()


@pytest.mark.asyncio
async def test_saving_regular_kb_still_reloads_it():
    from app.modules.data.manager import AgentRAGServiceManager

    manager = AgentRAGServiceManager()
    kb = KBRead(id=uuid.uuid4(), name="KB", type="text", content="Hello", extra_metadata={})

    with patch.object(manager, "get_service", new=AsyncMock(return_value=None)) as get_service:
        await manager.load_knowledge_items([kb], action="update")

    get_service.assert_awaited_once()


@pytest.mark.asyncio
async def test_cleared_copy_dates_recopy_existing_articles():
    kb_id = uuid.uuid4()
    kb = _make_kb(kb_id, extra_metadata={"content_format": "markdown", "salesforce_article_updated_at": {}})
    rag = _FakeRagManager(existing_ids=[f"KB:{kb_id}#article_ka-1"])
    body = '<p>See <a href="https://example.com/fees">fees</a>.</p>'

    result, _ = await _run_sync(kb, _make_datasource(), rag, articles=[_article("ka-1", body=body)])

    assert result["articles_updated"] == 1
    assert "[fees](https://example.com/fees)" in rag.added[0][1]


class _FailingRagManager(_FakeRagManager):
    def __init__(self, existing_ids=None, failing_ids=()):
        super().__init__(existing_ids)
        self.failing_ids = set(failing_ids)

    async def add_document(self, kb, doc_id, content, metadata):
        if doc_id in self.failing_ids:
            raise RuntimeError("embedding failed")
        return await super().add_document(kb, doc_id, content, metadata)


@pytest.mark.asyncio
async def test_failed_article_is_retried_alone():
    kb_id = uuid.uuid4()
    kb = _make_kb(kb_id, extra_metadata={"salesforce_article_updated_at": {}})
    existing = [f"KB:{kb_id}#article_ka-1", f"KB:{kb_id}#article_ka-2"]
    articles = [_article("ka-1"), _article("ka-2")]
    rag = _FailingRagManager(existing_ids=existing, failing_ids=[f"KB:{kb_id}#article_ka-1"])

    _, kb_service = await _run_sync(kb, _make_datasource(), rag, articles=articles)

    stored = _written_row(kb_service).extra_metadata
    assert set(stored["salesforce_article_updated_at"]) == {"ka-2"}

    retry_kb = _make_kb(kb_id, extra_metadata=stored)
    retry_rag = _FakeRagManager(existing_ids=[f"KB:{kb_id}#article_ka-2"])
    result, _ = await _run_sync(retry_kb, _make_datasource(), retry_rag, articles=articles)

    assert result["articles_added"] == 1
    assert result["articles_updated"] == 0
    assert [doc_id for doc_id, _, _ in retry_rag.added] == [f"KB:{kb_id}#article_ka-1"]


def _saved_kb(kb_type="salesforce", extra_metadata=None, rag_config=None):
    from app.schemas.agent_knowledge import KBBase

    return KBBase(name="SF KB", type=kb_type, extra_metadata=extra_metadata or {}, rag_config=rag_config)


def _stored_kb(extra_metadata, rag_config=None):
    return KBRead(id=uuid.uuid4(), name="SF KB", type="salesforce", extra_metadata=extra_metadata, rag_config=rag_config)


_DATES = {"salesforce_article_updated_at": {"ka-1": "2026-01-01T00:00:00Z"}}


@pytest.mark.parametrize(
    "stored_metadata, saved_metadata, stored_rag, saved_rag, dates_cleared",
    [
        ({**_DATES, "content_format": "text"}, {**_DATES, "content_format": "markdown"}, None, None, True),
        ({**_DATES, "content_format": "text"}, {**_DATES, "content_format": "text"}, None, None, False),
        ({**_DATES, "allow_html_content": True}, {**_DATES, "allow_html_content": True, "content_format": "html"}, None, None, False),
        ({**_DATES}, {**_DATES, "content_format": "text"}, None, None, False),
        ({**_DATES}, {**_DATES}, {"vector": {"chunk_size": 1000}}, {"vector": {"chunk_size": 500}}, True),
        ({**_DATES}, {**_DATES}, {"vector": {"chunk_size": 1000}}, None, False),
    ],
)
def test_save_clears_copy_dates_only_when_content_settings_change(stored_metadata, saved_metadata, stored_rag, saved_rag, dates_cleared):
    from app.tasks.salesforce_article_sync_tasks import clear_copy_dates_on_content_change

    saved = _saved_kb(extra_metadata=saved_metadata, rag_config=saved_rag)
    clear_copy_dates_on_content_change(_stored_kb(stored_metadata, stored_rag), saved)

    expected = {} if dates_cleared else _DATES["salesforce_article_updated_at"]
    assert saved.extra_metadata["salesforce_article_updated_at"] == expected


def test_save_of_other_kb_types_keeps_their_metadata():
    from app.tasks.salesforce_article_sync_tasks import clear_copy_dates_on_content_change

    saved = _saved_kb(kb_type="zendesk", extra_metadata={**_DATES, "content_format": "markdown"})
    clear_copy_dates_on_content_change(_stored_kb({**_DATES, "content_format": "text"}), saved)

    assert saved.extra_metadata["salesforce_article_updated_at"] == _DATES["salesforce_article_updated_at"]


@pytest.mark.parametrize(
    "body, content_format, expected",
    [
        ('<p><a href="/articles/Reset">Reset</a></p>', "markdown", "Reset"),
        ('<p><a href="#step-2">Step 2</a></p>', "markdown", "Step 2"),
        ('<p><a href="javascript:alert(1)">Click</a></p>', "markdown", "Click"),
        ('<p><a href="https://help.acme.com/x">Help</a></p>', "markdown", "[Help](https://help.acme.com/x)"),
        ('<p><a href="mailto:help@acme.com">Mail us</a></p>', "markdown", "[Mail us](mailto:help@acme.com)"),
        ('<p><a href="/articles/Reset">Reset</a></p>', "html", "<p>Reset</p>"),
        ('<P>Kept <a href="https://acme.com/x">as is</a></P>', "html", '<P>Kept <a href="https://acme.com/x">as is</a></P>'),
    ],
)
def test_only_full_links_are_kept(body, content_format, expected):
    from app.tasks.salesforce_article_sync_tasks import _parse_article_body

    assert _parse_article_body(body, content_format) == expected


@pytest.mark.asyncio
async def test_sync_writes_only_its_own_fields():
    kb = _make_kb(uuid.uuid4())
    saved_meanwhile = _stored_row(kb, name="Renamed KB", extra_metadata={"include_restricted_articles": True})

    _, kb_service = await _run_sync(
        kb, _make_datasource(), _FakeRagManager(), articles=[_article("ka-1")], current_row=saved_meanwhile
    )

    written = _written_row(kb_service)
    assert written.name == "Renamed KB"
    assert written.extra_metadata == {
        "include_restricted_articles": True,
        "salesforce_article_updated_at": {"ka-1": "2026-01-01T00:00:00Z"},
    }
    assert written.last_sync_status == "success"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "saved_change",
    [
        {"extra_metadata": {"content_format": "markdown", "salesforce_article_updated_at": {}}},
        {"rag_config": {"vector": {"chunk_size": 500}}, "extra_metadata": {"salesforce_article_updated_at": {}}},
    ],
)
async def test_settings_saved_during_sync_are_kept_and_recopied_next_time(saved_change):
    from app.tasks.salesforce_article_sync_tasks import SETTINGS_CHANGED_WARNING

    kb = _make_kb(uuid.uuid4(), extra_metadata={"salesforce_article_updated_at": {"ka-1": "2026-01-01T00:00:00Z"}})
    saved_meanwhile = _stored_row(kb, **saved_change)
    rag = _FakeRagManager(existing_ids=[f"KB:{kb.id}#article_ka-1"])

    result, kb_service = await _run_sync(
        kb, _make_datasource(), rag, articles=[_article("ka-1"), _article("ka-2")], current_row=saved_meanwhile
    )

    written = _written_row(kb_service)
    assert written.extra_metadata == saved_change["extra_metadata"]
    assert written.rag_config == saved_meanwhile.rag_config
    assert written.last_sync_status == "success_with_warnings"
    assert written.last_sync_error == SETTINGS_CHANGED_WARNING
    assert result["per_kb"][0]["status"] == "success_with_warnings"


@pytest.mark.asyncio
async def test_kb_deleted_during_sync_is_not_written():
    kb = _make_kb(uuid.uuid4())

    result, kb_service = await _run_sync(
        kb, _make_datasource(), _FakeRagManager(), articles=[_article("ka-1")], current_row=None
    )

    kb_service.repository.update.assert_not_awaited()
    assert result["per_kb"][0]["status"] == "success"


@pytest.mark.asyncio
async def test_result_is_written_onto_a_fresh_locked_row():
    from sqlalchemy.dialects import postgresql

    kb = _make_kb(uuid.uuid4())

    _, kb_service = await _run_sync(kb, _make_datasource(), _FakeRagManager(), articles=[_article("ka-1")])

    lookup = kb_service.repository.db.execute.await_args.args[0]
    assert "FOR NO KEY UPDATE" in str(lookup.compile(dialect=postgresql.dialect()))
    assert lookup.get_execution_options()["populate_existing"] is True


@pytest.mark.asyncio
async def test_save_reads_the_copy_dates_under_a_row_lock():
    from sqlalchemy.dialects import postgresql

    from app.tasks.salesforce_article_sync_tasks import apply_stored_copy_dates_on_save

    kb = _stored_kb({"content_format": "text", "salesforce_article_updated_at": {"ka-1": "2026-03-01T00:00:00Z"}})
    kb_service = _make_kb_service(kb)
    page = _saved_kb(extra_metadata={"content_format": "text", "salesforce_article_updated_at": {}})

    await apply_stored_copy_dates_on_save(kb_service, kb.id, page)

    lookup = kb_service.repository.db.execute.await_args.args[0]
    assert "FOR NO KEY UPDATE" in str(lookup.compile(dialect=postgresql.dialect()))
    assert page.extra_metadata["salesforce_article_updated_at"] == {"ka-1": "2026-03-01T00:00:00Z"}


@pytest.mark.asyncio
async def test_save_of_another_kb_type_takes_no_lock():
    from app.tasks.salesforce_article_sync_tasks import apply_stored_copy_dates_on_save

    kb_service = _make_kb_service(_stored_kb({}))
    page = _saved_kb(kb_type="zendesk", extra_metadata={"content_format": "text"})

    await apply_stored_copy_dates_on_save(kb_service, uuid.uuid4(), page)

    kb_service.repository.db.execute.assert_not_awaited()
    assert page.extra_metadata == {"content_format": "text"}


def test_save_from_an_older_page_keeps_the_stored_copy_dates():
    from app.tasks.salesforce_article_sync_tasks import clear_copy_dates_on_content_change

    stored = _stored_kb({"content_format": "markdown", "salesforce_article_updated_at": {"ka-1": "2026-03-01T00:00:00Z"}})
    older_page = _saved_kb(extra_metadata={"content_format": "markdown", "salesforce_article_updated_at": {"ka-1": "2026-01-01T00:00:00Z"}})

    clear_copy_dates_on_content_change(stored, older_page)

    assert older_page.extra_metadata["salesforce_article_updated_at"] == {"ka-1": "2026-03-01T00:00:00Z"}


def test_save_without_stored_copy_dates_does_not_add_them():
    from app.tasks.salesforce_article_sync_tasks import clear_copy_dates_on_content_change

    page = _saved_kb(extra_metadata={**_DATES, "content_format": "text"})
    clear_copy_dates_on_content_change(_stored_kb({"content_format": "text"}), page)

    assert "salesforce_article_updated_at" not in page.extra_metadata


def test_rag_defaults_filled_by_the_page_are_not_a_change():
    from app.tasks.salesforce_article_sync_tasks import _with_rag_editor_defaults, clear_copy_dates_on_content_change

    page = _saved_kb(extra_metadata={**_DATES}, rag_config=_with_rag_editor_defaults({}))
    clear_copy_dates_on_content_change(_stored_kb({**_DATES}, rag_config={}), page)

    assert page.extra_metadata["salesforce_article_updated_at"] == _DATES["salesforce_article_updated_at"]


def test_a_real_rag_change_after_the_defaults_still_clears_the_copy_dates():
    from app.tasks.salesforce_article_sync_tasks import _with_rag_editor_defaults, clear_copy_dates_on_content_change

    changed = _with_rag_editor_defaults({})
    changed["vector"]["chunk_size"] = 500
    page = _saved_kb(extra_metadata={**_DATES}, rag_config=changed)
    clear_copy_dates_on_content_change(_stored_kb({**_DATES}, rag_config={}), page)

    assert page.extra_metadata["salesforce_article_updated_at"] == {}


@pytest.mark.asyncio
async def test_rag_defaults_saved_during_sync_still_keep_the_copy_dates():
    from app.tasks.salesforce_article_sync_tasks import _with_rag_editor_defaults

    kb = _make_kb(uuid.uuid4())
    saved_meanwhile = _stored_row(kb, rag_config=_with_rag_editor_defaults({}))

    _, kb_service = await _run_sync(
        kb, _make_datasource(), _FakeRagManager(), articles=[_article("ka-1")], current_row=saved_meanwhile
    )

    written = _written_row(kb_service)
    assert written.extra_metadata["salesforce_article_updated_at"] == {"ka-1": "2026-01-01T00:00:00Z"}
    assert written.last_sync_status == "success"


@pytest.mark.asyncio
@pytest.mark.parametrize("include_restricted, reads_public_flag", [(False, True), (True, False)])
async def test_public_flag_is_read_only_for_public_only_kbs(include_restricted, reads_public_flag):
    from app.tasks.salesforce_article_sync_tasks import import_salesforce_articles_to_kb_async

    kb = _make_kb(uuid.uuid4(), extra_metadata={"include_restricted_articles": include_restricted})
    connector_patch, connector = _patch_connector(articles=[_article("ka-1")])
    with _patch_env(kb, _make_datasource(), _FakeRagManager(), _make_kb_service(kb), _make_app_settings_service()), connector_patch:
        await import_salesforce_articles_to_kb_async(kb_id=kb.id, sync_now=True)

    assert connector.fetch_knowledge_articles.await_args.kwargs["read_public_flag"] is reads_public_flag


@pytest.mark.parametrize(
    "stored_vector, saved_vector",
    [
        ({"enabled": True}, {"enabled": False}),
        ({"enabled": True, "vector_db_type": "pgvector"}, {"enabled": True, "vector_db_type": "qdrant"}),
    ],
)
def test_a_vector_setting_change_is_never_hidden_by_the_defaults(stored_vector, saved_vector):
    from app.tasks.salesforce_article_sync_tasks import clear_copy_dates_on_content_change

    page = _saved_kb(extra_metadata={**_DATES}, rag_config={"vector": saved_vector})
    clear_copy_dates_on_content_change(_stored_kb({**_DATES}, rag_config={"vector": stored_vector}), page)

    assert page.extra_metadata["salesforce_article_updated_at"] == {}


@pytest.mark.asyncio
async def test_each_kb_result_is_committed_right_after_it_is_written():
    from app.tasks.salesforce_article_sync_tasks import import_salesforce_articles_to_kb_async

    kb = _make_kb(uuid.uuid4())
    kb_service = _make_kb_service(kb)
    steps = MagicMock()
    steps.attach_mock(kb_service.repository.update, "write")
    steps.attach_mock(kb_service.transactions.commit, "commit")
    connector_patch, _ = _patch_connector(articles=[_article("ka-1")])

    with _patch_env(kb, _make_datasource(), _FakeRagManager(), kb_service, _make_app_settings_service()), connector_patch:
        await import_salesforce_articles_to_kb_async(kb_id=kb.id, sync_now=True)

    assert [name for name, _, _ in steps.mock_calls] == ["write", "commit"]


@pytest.mark.asyncio
async def test_a_failed_kb_rolls_back_its_own_work_before_recording_the_error():
    from app.tasks.salesforce_article_sync_tasks import import_salesforce_articles_to_kb_async

    kb = _make_kb(uuid.uuid4())
    kb_service = _make_kb_service(kb)
    steps = MagicMock()
    steps.attach_mock(kb_service.transactions.rollback, "rollback")
    steps.attach_mock(kb_service.repository.update, "write")
    steps.attach_mock(kb_service.transactions.commit, "commit")
    connector_patch, _ = _patch_connector(raise_exc=RuntimeError("boom"))

    with _patch_env(kb, _make_datasource(), _FakeRagManager(), kb_service, _make_app_settings_service()), connector_patch:
        await import_salesforce_articles_to_kb_async(kb_id=kb.id, sync_now=True)

    assert [name for name, _, _ in steps.mock_calls] == ["rollback", "write", "commit"]
    assert _written_row(kb_service).last_sync_status == "error"


def _record_writes(kb_service):
    """Record the copy dates and status of every write to the KB row."""
    writes = []

    def _write(row):
        dates = (row.extra_metadata or {}).get("salesforce_article_updated_at")
        writes.append((len(dates) if dates is not None else None, row.last_sync_status))
        return row

    kb_service.repository.update.side_effect = _write
    return writes


class _CutOffRagManager(_FakeRagManager):
    """Stops like the 15-minute task limit after a number of added articles."""

    def __init__(self, existing_ids=None, stop_after=0):
        super().__init__(existing_ids)
        self.stop_after = stop_after

    async def add_document(self, kb, doc_id, content, metadata):
        if len(self.added) == self.stop_after:
            raise asyncio.CancelledError()
        return await super().add_document(kb, doc_id, content, metadata)


async def _sync_with(kb, kb_service, rag, articles):
    from app.tasks.salesforce_article_sync_tasks import import_salesforce_articles_to_kb_async

    connector_patch, _ = _patch_connector(articles=articles)
    with _patch_env(kb, _make_datasource(), rag, kb_service, _make_app_settings_service()), connector_patch:
        return await import_salesforce_articles_to_kb_async(kb_id=kb.id, sync_now=True)


@pytest.mark.asyncio
async def test_progress_is_saved_every_50_articles_without_a_status():
    kb = _make_kb(uuid.uuid4())
    kb_service = _make_kb_service(kb)
    writes = _record_writes(kb_service)

    await _sync_with(kb, kb_service, _FakeRagManager(), [_article(f"ka-{n}") for n in range(120)])

    assert writes == [(50, None), (100, None), (120, "success")]
    assert kb_service.transactions.commit.await_count == 3


@pytest.mark.asyncio
async def test_a_cut_off_sync_keeps_its_progress_and_the_next_run_continues():
    kb = _make_kb(uuid.uuid4())
    kb_service = _make_kb_service(kb)
    articles = [_article(f"ka-{n}") for n in range(120)]
    rag = _CutOffRagManager(stop_after=70)

    with pytest.raises(asyncio.CancelledError):
        await _sync_with(kb, kb_service, rag, articles)

    stored_row = _written_row(kb_service)
    assert len(stored_row.extra_metadata["salesforce_article_updated_at"]) == 50
    assert stored_row.last_sync_status is None

    next_kb = _make_kb(kb.id, extra_metadata=stored_row.extra_metadata)
    next_rag = _FakeRagManager(existing_ids=[doc_id for doc_id, _, _ in rag.added])
    result = await _sync_with(next_kb, _make_kb_service(next_kb), next_rag, articles)

    assert result["articles_added"] == 50
    assert result["articles_updated"] == 20


@pytest.mark.asyncio
async def test_progress_is_not_saved_after_the_settings_changed():
    kb = _make_kb(uuid.uuid4())
    kb_service = _make_kb_service(kb, current_row=_stored_row(kb, extra_metadata={"content_format": "markdown"}))
    writes = _record_writes(kb_service)

    result = await _sync_with(kb, kb_service, _FakeRagManager(), [_article(f"ka-{n}") for n in range(120)])

    assert writes == [(None, "success_with_warnings")]
    assert result["per_kb"][0]["status"] == "success_with_warnings"


@pytest.mark.asyncio
async def test_each_kb_uses_its_settings_from_when_its_turn_starts():
    listed_kb = _make_kb(uuid.uuid4(), extra_metadata={"include_restricted_articles": True})
    turned_off_meanwhile = _stored_row(listed_kb, extra_metadata={"include_restricted_articles": False})
    kb_service = _make_kb_service(listed_kb, row_at_start=turned_off_meanwhile)
    rag = _FakeRagManager()

    await _sync_with(listed_kb, kb_service, rag, [_article("ka-public"), _article("ka-internal", is_public=False)])

    assert [doc_id for doc_id, _, _ in rag.added] == [f"KB:{listed_kb.id}#article_ka-public"]


@pytest.mark.asyncio
async def test_kb_deleted_before_its_turn_is_skipped():
    kb = _make_kb(uuid.uuid4())
    kb_service = _make_kb_service(kb)
    deleted = MagicMock()
    deleted.scalars.return_value.first.return_value = None
    kb_service.repository.db.execute = AsyncMock(return_value=deleted)

    result = await _sync_with(kb, kb_service, _FakeRagManager(), [_article("ka-1")])

    assert result["per_kb"] == [{"kb_id": str(kb.id), "name": kb.name, "status": "skipped", "reason": "not_found"}]
    kb_service.repository.update.assert_not_awaited()
