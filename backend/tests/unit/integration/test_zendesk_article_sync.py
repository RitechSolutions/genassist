"""Unit tests for which Zendesk articles the knowledge sync copies (all services faked)."""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schemas.agent_knowledge import KBRead
from app.services.agent_knowledge import KnowledgeBaseService
from app.services.datasources import DataSourceService

TASK_MODULE = "app.tasks.zendesk_article_sync_tasks"


def _article(article_id, draft=False, segment_id=None, segment_ids=None):
    return {
        "id": article_id,
        "title": f"Article {article_id}",
        "body": f"<p>Body {article_id}</p>",
        "draft": draft,
        "user_segment_id": segment_id,
        "user_segment_ids": segment_ids or [],
        "updated_at": "2026-01-01T00:00:00Z",
        "html_url": f"https://help.example.com/articles/{article_id}",
        "locale": "en-us",
        "section_id": 1,
    }


PUBLIC = _article(1)
SIGNED_IN_ONLY = _article(2, segment_id=900)
STAFF_ONLY = _article(3, segment_id=901)
GROUP_ONLY = _article(4, segment_ids=[902])
DRAFT = _article(5, draft=True)


class _FakeRagManager:
    def __init__(self, existing_ids=None):
        self.existing = list(existing_ids or [])
        self.added = []
        self.deleted = []

    async def get_document_ids(self, kb):
        return list(self.existing)

    async def add_document(self, kb, doc_id, content, metadata, **_):
        self.added.append(doc_id)
        return {"vector": True}

    async def delete_document(self, kb, doc_id):
        self.deleted.append(doc_id)
        return {"vector": True}


def _make_kb(kb_id, extra_metadata=None):
    return KBRead(
        id=kb_id,
        name="ZD KB",
        type="zendesk",
        sync_active=True,
        sync_source_id=uuid.uuid4(),
        extra_metadata=extra_metadata or {},
    )


async def _run_sync(kb, rag, articles):
    from app.tasks.zendesk_article_sync_tasks import import_zendesk_articles_to_kb_async

    kb_service = MagicMock()
    kb_service.get_by_id = AsyncMock(return_value=kb)
    kb_service.update = AsyncMock(return_value=kb)
    ds_service = MagicMock()
    ds_service.get_by_id = AsyncMock(
        return_value=SimpleNamespace(
            name="ZD DS",
            source_type="zendesk",
            connection_data={"subdomain": "acme", "email": "a@example.com", "api_token": "t"},
        )
    )

    def _get(dependency):
        if dependency is KnowledgeBaseService:
            return kb_service
        if dependency is DataSourceService:
            return ds_service
        return rag

    connector = MagicMock()
    connector._require_credentials = MagicMock()
    if isinstance(articles, Exception):
        connector.fetch_articles = AsyncMock(side_effect=articles)
    else:
        connector.fetch_articles = AsyncMock(return_value=articles)
    with patch(f"{TASK_MODULE}.injector") as fake_injector, patch(f"{TASK_MODULE}.ZendeskConnector", return_value=connector):
        fake_injector.get.side_effect = _get
        result = await import_zendesk_articles_to_kb_async(kb_id=kb.id, sync_now=True)
    return result, kb_service


def _doc(kb_id, article):
    return f"KB:{kb_id}#article_{article['id']}"


@pytest.mark.asyncio
async def test_only_published_articles_visible_to_everyone_are_copied():
    kb_id = uuid.uuid4()
    rag = _FakeRagManager()

    await _run_sync(_make_kb(kb_id), rag, [PUBLIC, SIGNED_IN_ONLY, STAFF_ONLY, GROUP_ONLY, DRAFT])

    assert rag.added == [_doc(kb_id, PUBLIC)]


@pytest.mark.asyncio
async def test_include_restricted_articles_copies_segmented_ones_but_not_drafts():
    kb_id = uuid.uuid4()
    rag = _FakeRagManager()

    await _run_sync(_make_kb(kb_id, {"include_restricted_articles": True}), rag, [PUBLIC, SIGNED_IN_ONLY, GROUP_ONLY, DRAFT])

    assert sorted(rag.added) == sorted(_doc(kb_id, a) for a in [PUBLIC, SIGNED_IN_ONLY, GROUP_ONLY])


@pytest.mark.asyncio
async def test_include_unpublished_articles_still_copies_public_drafts_only():
    kb_id = uuid.uuid4()
    rag = _FakeRagManager()

    await _run_sync(_make_kb(kb_id, {"allow_unpublished_articles": True}), rag, [PUBLIC, DRAFT, STAFF_ONLY])

    assert sorted(rag.added) == sorted(_doc(kb_id, a) for a in [PUBLIC, DRAFT])


@pytest.mark.asyncio
async def test_restricted_articles_already_copied_are_removed():
    kb_id = uuid.uuid4()
    rag = _FakeRagManager(existing_ids=[_doc(kb_id, PUBLIC), _doc(kb_id, SIGNED_IN_ONLY), _doc(kb_id, STAFF_ONLY)])

    result, _ = await _run_sync(_make_kb(kb_id), rag, [PUBLIC, SIGNED_IN_ONLY, STAFF_ONLY])

    assert {_doc(kb_id, SIGNED_IN_ONLY), _doc(kb_id, STAFF_ONLY)} <= set(rag.deleted)
    assert rag.added == [_doc(kb_id, PUBLIC)]
    assert result["articles_deleted"] == 2


@pytest.mark.asyncio
async def test_all_restricted_reply_still_removes_copies():
    kb_id = uuid.uuid4()
    rag = _FakeRagManager(existing_ids=[_doc(kb_id, STAFF_ONLY)])

    await _run_sync(_make_kb(kb_id), rag, [STAFF_ONLY])

    assert rag.deleted == [_doc(kb_id, STAFF_ONLY)]


@pytest.mark.asyncio
async def test_empty_reply_from_zendesk_keeps_existing_copies():
    kb_id = uuid.uuid4()
    rag = _FakeRagManager(existing_ids=[_doc(kb_id, PUBLIC)])

    result, kb_service = await _run_sync(_make_kb(kb_id), rag, [])

    assert rag.deleted == []
    assert kb_service.update.await_args.args[1].last_sync_status == "success"


@pytest.mark.asyncio
async def test_failed_fetch_keeps_existing_copies():
    kb_id = uuid.uuid4()
    rag = _FakeRagManager(existing_ids=[_doc(kb_id, PUBLIC), _doc(kb_id, STAFF_ONLY)])

    _, kb_service = await _run_sync(_make_kb(kb_id), rag, RuntimeError("Zendesk API error 503"))

    assert rag.deleted == []
    assert kb_service.update.await_args.args[1].last_sync_status == "error"


class _FailingLoadRagManager(_FakeRagManager):
    """Reports a failed load for the given articles, the way an embedding outage does."""

    def __init__(self, failing_articles, existing_ids=None):
        super().__init__(existing_ids)
        self.failing_ids = {f"article_{article['id']}" for article in failing_articles}

    async def add_document(self, kb, doc_id, content, metadata, **_):
        await super().add_document(kb, doc_id, content, metadata)
        return {"vector": doc_id.rsplit("#", 1)[-1] not in self.failing_ids}


@pytest.mark.asyncio
async def test_failed_load_is_an_error_not_an_added_article():
    kb = _make_kb(uuid.uuid4())
    second = _article(6)
    rag = _FailingLoadRagManager(failing_articles=[second])

    result, kb_service = await _run_sync(kb, rag, [PUBLIC, second])

    assert result["articles_added"] == 1
    saved = kb_service.update.await_args.args[1]
    assert saved.last_sync_status == "success_with_warnings"
    assert saved.last_sync_error.startswith("1 of 2 articles could not be copied")
    assert set(saved.extra_metadata["zendesk_article_updated_at"]) == {str(PUBLIC["id"])}


@pytest.mark.asyncio
async def test_sync_where_every_load_fails_ends_in_error():
    kb = _make_kb(uuid.uuid4())
    rag = _FailingLoadRagManager(failing_articles=[PUBLIC])

    result, kb_service = await _run_sync(kb, rag, [PUBLIC])

    assert result["articles_added"] == 0
    saved = kb_service.update.await_args.args[1]
    assert saved.last_sync_status == "error"
    assert saved.extra_metadata["zendesk_article_updated_at"] == {}


class _PartlyLoadingRagManager(_FakeRagManager):
    """One store takes every article and the other refuses it."""

    async def add_document(self, kb, doc_id, content, metadata, **_):
        await super().add_document(kb, doc_id, content, metadata)
        return {"vector": True, "legra": False}


@pytest.mark.asyncio
async def test_partly_loaded_article_is_counted_and_reported_as_a_warning():
    kb = _make_kb(uuid.uuid4())

    result, kb_service = await _run_sync(kb, _PartlyLoadingRagManager(), [PUBLIC])

    assert result["articles_added"] == 1
    saved = kb_service.update.await_args.args[1]
    assert saved.last_sync_status == "success_with_warnings"
    assert "was loaded but is missing from: legra" in saved.last_sync_error
    assert "could not be copied" not in saved.last_sync_error
    assert set(saved.extra_metadata["zendesk_article_updated_at"]) == {str(PUBLIC["id"])}


@pytest.mark.asyncio
async def test_partly_loaded_article_is_not_copied_again_on_the_next_sync():
    kb_id = uuid.uuid4()
    _, kb_service = await _run_sync(_make_kb(kb_id), _PartlyLoadingRagManager(), [PUBLIC])
    saved_dates = kb_service.update.await_args.args[1].extra_metadata["zendesk_article_updated_at"]
    kb = _make_kb(kb_id, extra_metadata={"zendesk_article_updated_at": saved_dates})
    rag = _PartlyLoadingRagManager(existing_ids=[_doc(kb_id, PUBLIC)])

    result, _ = await _run_sync(kb, rag, [PUBLIC])

    assert rag.added == []
    assert rag.deleted == []
    assert result["articles_updated"] == 0


@pytest.mark.asyncio
async def test_failed_update_keeps_the_old_copy_date_so_it_is_retried():
    kb_id = uuid.uuid4()
    kb = _make_kb(kb_id, extra_metadata={"zendesk_article_updated_at": {str(PUBLIC["id"]): "2025-12-01T00:00:00Z"}})
    rag = _FailingLoadRagManager(failing_articles=[PUBLIC], existing_ids=[_doc(kb_id, PUBLIC)])

    result, kb_service = await _run_sync(kb, rag, [PUBLIC])

    assert result["articles_updated"] == 0
    saved = kb_service.update.await_args.args[1]
    assert saved.last_sync_status == "success_with_warnings"
    assert saved.last_sync_error.startswith("1 of 1 articles could not be copied")
    assert saved.extra_metadata["zendesk_article_updated_at"] == {str(PUBLIC["id"]): "2025-12-01T00:00:00Z"}


class _UnreachableRagManager(_FakeRagManager):
    """Answers the way the manager does when the stores of the knowledge base cannot be reached."""

    async def add_document(self, kb, doc_id, content, metadata, **_):
        return {}


@pytest.mark.asyncio
async def test_unreachable_stores_end_in_error_and_nothing_is_counted():
    kb = _make_kb(uuid.uuid4())

    result, kb_service = await _run_sync(kb, _UnreachableRagManager(), [PUBLIC])

    assert result["articles_added"] == 0
    saved = kb_service.update.await_args.args[1]
    assert saved.last_sync_status == "error"
    assert "no store reached" in saved.last_sync_error
    assert saved.extra_metadata["zendesk_article_updated_at"] == {}


@pytest.mark.asyncio
async def test_failed_new_article_on_a_filled_knowledge_base_is_a_warning_not_an_error():
    kb_id = uuid.uuid4()
    copied_before = _article(7)
    kb = _make_kb(kb_id, extra_metadata={"zendesk_article_updated_at": {"7": copied_before["updated_at"]}})
    rag = _FailingLoadRagManager(failing_articles=[PUBLIC], existing_ids=[_doc(kb_id, copied_before)])

    result, kb_service = await _run_sync(kb, rag, [copied_before, PUBLIC])

    assert result["articles_added"] == 0
    assert rag.deleted == []
    saved = kb_service.update.await_args.args[1]
    assert saved.last_sync_status == "success_with_warnings"
    assert saved.last_sync_error.startswith("1 of 1 articles could not be copied")
    assert set(saved.extra_metadata["zendesk_article_updated_at"]) == {"7"}


@pytest.mark.asyncio
async def test_successful_sync_records_its_time_as_the_last_successful_sync():
    result, kb_service = await _run_sync(_make_kb(uuid.uuid4()), _FakeRagManager(), [PUBLIC])

    saved = kb_service.update.await_args.args[1]
    assert saved.last_sync_status == "success"
    assert saved.last_successful_sync is not None
    assert saved.last_successful_sync == saved.last_synced
    assert result["kbs_failed"] == 0


@pytest.mark.asyncio
async def test_failed_sync_keeps_the_last_successful_sync():
    result, kb_service = await _run_sync(_make_kb(uuid.uuid4()), _FakeRagManager(), RuntimeError("Zendesk is down"))

    saved = kb_service.update.await_args.args[1]
    assert saved.last_sync_status == "error"
    assert saved.last_synced is not None  # still moves: it schedules the next run
    assert saved.last_successful_sync is None
    assert result["kbs_failed"] == 1


COPY_DATES = {"zendesk_article_updated_at": {str(PUBLIC["id"]): "2026-01-01T00:00:00Z"}}
BY_SIZE = {"vector": {"chunk_strategy": "recursive"}}
BY_SECTIONS = {"vector": {"chunk_strategy": "sections"}}


def _stored_kb(kb_id, extra_metadata, rag_config=None):
    return _make_kb(kb_id, extra_metadata=extra_metadata).model_copy(update={"rag_config": rag_config})


def _saved_page(extra_metadata, rag_config=None):
    from app.schemas.agent_knowledge import KBBase

    return KBBase(name="ZD KB", type="zendesk", extra_metadata=extra_metadata, rag_config=rag_config)


def test_chunking_change_on_save_clears_the_copy_dates():
    from app.tasks.salesforce_article_sync_tasks import clear_copy_dates_on_content_change

    page = _saved_page({**COPY_DATES}, rag_config=BY_SECTIONS)
    clear_copy_dates_on_content_change(_stored_kb(uuid.uuid4(), {**COPY_DATES}, rag_config=BY_SIZE), page)

    assert page.extra_metadata["zendesk_article_updated_at"] == {}


def test_content_format_change_on_save_clears_the_copy_dates():
    from app.tasks.salesforce_article_sync_tasks import clear_copy_dates_on_content_change

    page = _saved_page({**COPY_DATES, "content_format": "markdown"})
    clear_copy_dates_on_content_change(_stored_kb(uuid.uuid4(), {**COPY_DATES, "content_format": "text"}), page)

    assert page.extra_metadata["zendesk_article_updated_at"] == {}


def test_save_without_content_changes_keeps_the_stored_copy_dates():
    from app.tasks.salesforce_article_sync_tasks import clear_copy_dates_on_content_change

    older_page = _saved_page({"zendesk_article_updated_at": {"1": "2025-06-01T00:00:00Z"}}, rag_config=BY_SIZE)
    clear_copy_dates_on_content_change(_stored_kb(uuid.uuid4(), {**COPY_DATES}, rag_config=BY_SIZE), older_page)

    assert older_page.extra_metadata["zendesk_article_updated_at"] == COPY_DATES["zendesk_article_updated_at"]


@pytest.mark.asyncio
async def test_save_reads_the_copy_dates_under_a_row_lock():
    from sqlalchemy.dialects import postgresql

    from app.tasks.salesforce_article_sync_tasks import apply_stored_copy_dates_on_save

    kb_id = uuid.uuid4()
    stored_row = SimpleNamespace(extra_metadata={**COPY_DATES}, rag_config=BY_SIZE)
    lookup = MagicMock()
    lookup.scalars.return_value.first.return_value = stored_row
    kb_service = MagicMock()
    kb_service.repository.db.execute = AsyncMock(return_value=lookup)
    page = _saved_page({"zendesk_article_updated_at": {}}, rag_config=BY_SIZE)

    await apply_stored_copy_dates_on_save(kb_service, kb_id, page)

    statement = kb_service.repository.db.execute.await_args.args[0]
    assert "FOR NO KEY UPDATE" in str(statement.compile(dialect=postgresql.dialect()))
    assert page.extra_metadata["zendesk_article_updated_at"] == COPY_DATES["zendesk_article_updated_at"]


@pytest.mark.asyncio
async def test_after_a_chunking_change_the_next_sync_copies_every_article_again():
    from app.tasks.salesforce_article_sync_tasks import clear_copy_dates_on_content_change

    kb_id = uuid.uuid4()
    _, kb_service = await _run_sync(_stored_kb(kb_id, {}, rag_config=BY_SIZE), _FakeRagManager(), [PUBLIC])
    after_first_sync = kb_service.update.await_args.args[1].extra_metadata
    page = _saved_page(dict(after_first_sync), rag_config=BY_SECTIONS)
    clear_copy_dates_on_content_change(_stored_kb(kb_id, after_first_sync, rag_config=BY_SIZE), page)
    rag = _FakeRagManager(existing_ids=[_doc(kb_id, PUBLIC)])

    result, _ = await _run_sync(_stored_kb(kb_id, page.extra_metadata, rag_config=BY_SECTIONS), rag, [PUBLIC])

    assert rag.added == [_doc(kb_id, PUBLIC)]
    assert result["articles_updated"] == 1


class _MetadataRecordingRagManager(_FakeRagManager):
    def __init__(self, existing_ids=None):
        super().__init__(existing_ids)
        self.metadata = {}

    async def add_document(self, kb, doc_id, content, metadata, **_):
        self.metadata[doc_id] = metadata
        return await super().add_document(kb, doc_id, content, metadata)


@pytest.mark.asyncio
async def test_new_article_is_stored_with_its_title_as_the_document_title():
    kb_id = uuid.uuid4()
    rag = _MetadataRecordingRagManager()

    await _run_sync(_make_kb(kb_id), rag, [PUBLIC])

    assert rag.metadata[_doc(kb_id, PUBLIC)]["document_title"] == PUBLIC["title"]


@pytest.mark.asyncio
async def test_updated_article_is_stored_with_its_title_as_the_document_title():
    kb_id = uuid.uuid4()
    kb = _make_kb(kb_id, extra_metadata={"zendesk_article_updated_at": {str(PUBLIC["id"]): "2025-12-01T00:00:00Z"}})
    rag = _MetadataRecordingRagManager(existing_ids=[_doc(kb_id, PUBLIC)])

    await _run_sync(kb, rag, [PUBLIC])

    assert rag.metadata[_doc(kb_id, PUBLIC)]["document_title"] == PUBLIC["title"]
