"""A text, file or URL knowledge base shows how its indexing after a save went: indexing, success or error."""

import datetime
import logging
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.dialects import postgresql

from app.api.v1.routes import agent_knowledge as route_module
from app.modules.data import manager as manager_module
from app.modules.data.load_result import (
    INDEXING_STATUS,
    document_label,
    indexing_outcome,
    indexing_started_fields,
)
from app.modules.data.manager import (
    FILE_NOT_STORED_ERROR,
    FILE_UNREADABLE_ERROR,
    STORES_UNAVAILABLE_ERROR,
    AgentRAGServiceManager,
)
from app.schemas.agent_knowledge import KBBase, KBRead
from app.services import agent_knowledge_utils
from app.services.agent_knowledge_utils import (
    INDEXING_STOPPED_MESSAGE,
    NEWER_SAVE,
    OUTCOME_WRITE_ATTEMPTS,
    OWN_SAVE,
    SAVE_NOT_VISIBLE,
    IndexingOutcomeNotRecorded,
    index_saved_knowledge_base,
    mark_indexing_started,
    record_indexing_outcome,
    save_seen_on_row,
)

KB_ID = uuid.uuid4()
SAVED_AT = datetime.datetime(2026, 1, 5, 9, 0, tzinfo=datetime.timezone.utc)
LATER_SAVE_AT = SAVED_AT + datetime.timedelta(minutes=1)
CONTENT_ID = f"KB:{KB_ID}#content"
GUIDE_ID = f"KB:{KB_ID}#file_0:/data/uploads/acme-guide.pdf"
PRICES_ID = f"KB:{KB_ID}#file_1:https://files.example.com/globex-prices.docx?X-Amz-Signature=abc123"


def _saved_kb(kb_type="text", **fields):
    values = {"last_synced": SAVED_AT, "last_sync_status": INDEXING_STATUS, "last_sync_error": "", **fields}
    content = {"name": "Acme help centre", "content": "Acme help text", "extra_metadata": {}}
    return KBRead(id=KB_ID, type=kb_type, **content, **values)


def _row(**fields):
    values = {"last_synced": SAVED_AT, "last_sync_status": INDEXING_STATUS, "last_sync_error": "", **fields}
    return SimpleNamespace(id=KB_ID, type=values.pop("type", "text"), last_successful_sync=None, **values)


# ---- outcome of the loaded documents

def test_every_document_stored_is_a_success():
    results = [{"id": GUIDE_ID, "result": {"vector": True}}, {"id": PRICES_ID, "result": {"vector": True}}]

    assert indexing_outcome(results) == ("success", "")


def test_no_document_stored_is_an_error_with_the_reason():
    results = [{"id": CONTENT_ID, "result": {"vector": False}}]

    status, message = indexing_outcome(results)

    assert status == "error"
    assert message == (
        "1 of 1 documents could not be indexed: The content was not loaded into the knowledge base (vector)"
    )


def test_some_documents_failing_is_a_success_with_warnings():
    results = [
        {"id": GUIDE_ID, "result": {"vector": True}},
        {"id": PRICES_ID, "name": "Globex prices 2026.docx", "result": {}, "error": FILE_UNREADABLE_ERROR},
    ]

    status, message = indexing_outcome(results)

    assert status == "success_with_warnings"
    assert message == "1 of 2 documents could not be indexed: Globex prices 2026.docx: the file could not be read"


def test_a_document_missing_from_one_store_is_a_success_with_warnings():
    results = [{"id": CONTENT_ID, "result": {"vector": True, "legra": False}}]

    assert indexing_outcome(results) == ("success_with_warnings", "The content was loaded but is missing from: legra")


def test_nothing_to_index_is_an_error():
    assert indexing_outcome([]) == ("error", "Nothing was indexed")


@pytest.mark.parametrize(
    "document_id, label",
    [
        (f"KB:{KB_ID}", "The knowledge base"),
        (CONTENT_ID, "The content"),
        (GUIDE_ID, "acme-guide.pdf"),
        (PRICES_ID, "globex-prices.docx"),
        (f"KB:{KB_ID}#file_2:", "File 3"),
    ],
)
def test_document_label_is_short_and_leaves_out_links(document_id, label):
    assert document_label(document_id) == label


# ---- the save starts the indexing

def test_indexing_started_fields_replace_the_previous_outcome():
    assert indexing_started_fields(now=SAVED_AT) == {
        "last_synced": SAVED_AT,
        "last_sync_status": INDEXING_STATUS,
        "last_sync_error": "",
    }


@pytest.mark.parametrize("kb_type", ["text", "file", "url"])
def test_a_save_marks_the_knowledge_base_as_indexing_whatever_the_client_sent(kb_type):
    sent_by_client = KBBase(
        name="Acme help centre",
        type=kb_type,
        last_sync_status="success",
        last_sync_error="",
        last_synced=SAVED_AT - datetime.timedelta(days=30),
        last_successful_sync=SAVED_AT - datetime.timedelta(days=30),
    )

    mark_indexing_started(sent_by_client)

    assert sent_by_client.last_sync_status == INDEXING_STATUS
    assert sent_by_client.last_sync_error == ""
    assert sent_by_client.last_synced > SAVED_AT.replace(tzinfo=None)
    assert "last_successful_sync" not in sent_by_client.model_dump(exclude_none=True)


def test_a_new_save_clears_an_old_failure():
    resaved = KBBase(name="Acme help centre", type="file", last_sync_status="error", last_sync_error="old failure")

    mark_indexing_started(resaved)

    written = resaved.model_dump(exclude_none=True)
    assert written["last_sync_status"] == INDEXING_STATUS
    assert written["last_sync_error"] == ""


@pytest.mark.parametrize("kb_type", ["zendesk", "salesforce", "s3", "sharepoint", "database"])
def test_other_types_keep_the_sync_fields_of_the_save(kb_type):
    incoming = KBBase(name="Acme help centre", type=kb_type, last_sync_status="success", last_sync_error="kept")

    mark_indexing_started(incoming)

    assert (incoming.last_sync_status, incoming.last_sync_error, incoming.last_synced) == ("success", "kept", None)


async def _update_through_route(incoming):
    current = KBRead(id=KB_ID, name="Acme help centre", type=incoming.type, extra_metadata={})
    knowledge_service = AsyncMock()
    knowledge_service.get_by_id = AsyncMock(return_value=current)
    knowledge_service.update = AsyncMock(return_value=current)
    with patch.object(route_module, "schedule_rag_load"), patch.object(
        route_module, "populate_remote_file_metadata", new=AsyncMock()
    ), patch.object(route_module, "keep_loaded_files_on_save", new=AsyncMock()), patch.object(
        route_module, "apply_stored_copy_dates_on_save", new=AsyncMock()
    ):
        await route_module.update_knowledge_item(
            KB_ID,
            incoming,
            knowledge_service=knowledge_service,
            rag_manager=AsyncMock(),
            file_manager_service=AsyncMock(),
        )
    return knowledge_service.update.await_args.args[1]


@pytest.mark.asyncio
async def test_update_route_saves_indexing_instead_of_the_status_the_client_sent():
    incoming = KBBase(name="Acme help centre", type="text", content="Acme help text", last_sync_status="success")

    saved_item = await _update_through_route(incoming)

    assert saved_item.last_sync_status == INDEXING_STATUS


@pytest.mark.asyncio
async def test_create_route_saves_indexing():
    incoming = route_module.KBCreate(name="Acme help centre", type="text", content="Acme help text")
    knowledge_service = AsyncMock()
    knowledge_service.create = AsyncMock(return_value=_saved_kb())
    with patch.object(route_module, "schedule_rag_load") as schedule, patch.object(
        route_module, "populate_remote_file_metadata", new=AsyncMock()
    ):
        await route_module.create_knowledge_item(
            incoming, knowledge_service=knowledge_service, rag_manager=AsyncMock(), file_manager_service=AsyncMock()
        )

    assert knowledge_service.create.await_args.args[0].last_sync_status == INDEXING_STATUS
    schedule.assert_called_once()


# ---- the background indexing records its outcome

async def _index(load, kb=None, write_result=None):
    """Run the background indexing with a stand-in for the tenant-scoped write; returns what was recorded."""
    rag_manager = SimpleNamespace(load_knowledge_items=load)
    recorded = {}

    async def run_in_scope(task, task_name, tenant_id, **arguments):
        recorded.update(task=task, tenant_id=tenant_id, **arguments)
        return write_result or {"status": "success"}

    with patch("app.tasks.base.run_task_for_tenant", new=run_in_scope):
        await index_saved_knowledge_base(rag_manager, kb or _saved_kb(), "update", "acme")
    return recorded


@pytest.mark.asyncio
async def test_indexing_that_stores_every_document_is_recorded_as_success():
    recorded = await _index(AsyncMock(return_value=[{"id": CONTENT_ID, "result": {"vector": True}}]))

    assert (recorded["status"], recorded["message"]) == ("success", "")
    assert recorded["task"] is record_indexing_outcome
    assert recorded["tenant_id"] == "acme"
    assert recorded["started_kb"].id == KB_ID


@pytest.mark.asyncio
async def test_indexing_that_stores_nothing_is_recorded_as_failed_with_the_reason():
    recorded = await _index(AsyncMock(return_value=[{"id": CONTENT_ID, "result": {"vector": False}}]))

    assert recorded["status"] == "error"
    assert "The content was not loaded into the knowledge base (vector)" in recorded["message"]


@pytest.mark.asyncio
async def test_indexing_that_crashes_is_recorded_as_failed_in_plain_words(caplog):
    crash = ConnectionError("could not reach postgresql://acme_user:hunter2@db-host:5432/core_db")

    with caplog.at_level(logging.ERROR):
        recorded = await _index(AsyncMock(side_effect=crash))

    assert (recorded["status"], recorded["message"]) == ("error", INDEXING_STOPPED_MESSAGE)
    assert "db-host" not in recorded["message"]
    assert "RAG update task failed" in caplog.text


@pytest.mark.asyncio
async def test_a_long_failure_message_is_capped():
    many_failures = [{"id": f"KB:{KB_ID}#file_{index}:/data/{'x' * 200}.pdf", "result": {}} for index in range(5)]

    recorded = await _index(AsyncMock(return_value=many_failures))

    assert recorded["status"] == "error"
    assert len(recorded["message"]) < 540


@pytest.mark.asyncio
@pytest.mark.parametrize("kb_type", ["zendesk", "s3", "database"])
async def test_other_types_record_nothing_after_the_load(kb_type):
    load = AsyncMock(return_value=[])

    recorded = await _index(load, kb=_saved_kb(kb_type))

    load.assert_awaited_once()
    assert recorded == {}


@pytest.mark.asyncio
async def test_an_outcome_that_cannot_be_written_is_logged_as_an_error_with_the_knowledge_base(caplog):
    load = AsyncMock(return_value=[{"id": CONTENT_ID, "result": {"vector": True}}])
    write_failed = {"status": "failed", "error": "connection to the database was lost"}

    with caplog.at_level(logging.ERROR):
        await _index(load, write_result=write_failed)

    error_lines = [record.getMessage() for record in caplog.records if record.levelno == logging.ERROR]
    assert error_lines == [
        f"Could not record the indexing outcome (success) of KB {KB_ID}; "
        "its status stays Indexing until it is saved again: connection to the database was lost"
    ]


# ---- the outcome is written only onto the row state its own save left

def _read(row):
    result = MagicMock()
    result.scalars.return_value.first.return_value = row
    return result


async def _record(rows_read, started_kb=None, status="success", message=""):
    """Record an outcome against the rows each read of the knowledge base returns; returns the repository."""
    database = SimpleNamespace(execute=AsyncMock(side_effect=[_read(row) for row in rows_read]), rollback=AsyncMock())
    repository = SimpleNamespace(db=database, update=AsyncMock())
    injector = MagicMock(get=lambda cls: SimpleNamespace(repository=repository))
    with patch("app.dependencies.injector.injector", injector), patch.object(
        agent_knowledge_utils, "OUTCOME_RETRY_SECONDS", 0
    ):
        await record_indexing_outcome(started_kb or _saved_kb(), status, message)
    return repository


@pytest.mark.asyncio
async def test_success_is_written_on_the_knowledge_base_row():
    row = _row()

    repository = await _record([row])

    assert (row.last_sync_status, row.last_sync_error) == ("success", "")
    assert row.last_successful_sync is not None
    repository.update.assert_awaited_once_with(row)


@pytest.mark.asyncio
async def test_the_row_is_read_locked_for_the_write():
    repository = await _record([_row()])

    statement = repository.db.execute.await_args.args[0]
    assert "FOR NO KEY UPDATE" in str(statement.compile(dialect=postgresql.dialect()))


@pytest.mark.asyncio
async def test_failure_is_written_with_its_reason_and_keeps_the_last_success_date():
    row = _row()

    reason = "1 of 1 documents could not be indexed: The content: no readable text"

    await _record([row], status="error", message=reason)

    assert row.last_sync_status == "error"
    assert row.last_sync_error == reason
    assert row.last_successful_sync is None


@pytest.mark.asyncio
async def test_outcome_of_an_older_indexing_does_not_touch_a_newer_save():
    row = _row(last_synced=LATER_SAVE_AT)

    repository = await _record([row], status="error", message="older failure")

    assert (row.last_sync_status, row.last_sync_error, row.last_synced) == (INDEXING_STATUS, "", LATER_SAVE_AT)
    repository.update.assert_not_awaited()
    repository.db.rollback.assert_not_awaited()


@pytest.mark.asyncio
async def test_the_newer_indexing_still_writes_after_the_older_one_was_skipped():
    row = _row(last_synced=LATER_SAVE_AT)

    await _record([row], started_kb=_saved_kb(last_synced=SAVED_AT), status="error", message="older failure")
    await _record([row], started_kb=_saved_kb(last_synced=LATER_SAVE_AT), status="success")

    assert (row.last_sync_status, row.last_sync_error) == ("success", "")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "first_read",
    [None, _row(last_synced=SAVED_AT - datetime.timedelta(days=1), last_sync_status="success")],
    ids=["row not created yet", "row still shows the previous save"],
)
async def test_a_save_that_is_not_committed_yet_is_waited_for(first_read):
    row = _row()

    repository = await _record([first_read, row])

    assert row.last_sync_status == "success"
    repository.db.rollback.assert_awaited_once()
    repository.update.assert_awaited_once_with(row)
    if first_read is not None:
        assert first_read.last_sync_status == "success"


@pytest.mark.asyncio
async def test_a_save_that_never_shows_up_ends_in_an_error():
    with pytest.raises(IndexingOutcomeNotRecorded, match=f"not found in {OUTCOME_WRITE_ATTEMPTS} reads"):
        await _record([None] * OUTCOME_WRITE_ATTEMPTS)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "changed_row",
    [_row(type="s3"), _row(last_sync_status="success"), _row(last_sync_status="error", last_sync_error="kept")],
    ids=["switched to a synced type", "already ready", "already failed"],
)
async def test_a_row_that_no_longer_waits_for_this_outcome_is_left_alone(changed_row):
    status_before = (changed_row.last_sync_status, changed_row.last_sync_error)

    repository = await _record([changed_row], status="error", message="text indexing failed")

    assert (changed_row.last_sync_status, changed_row.last_sync_error) == status_before
    repository.update.assert_not_awaited()


def test_the_time_a_save_writes_is_recognised_after_the_database_returns_it():
    written_by_save = indexing_started_fields()["last_synced"]
    read_from_database = written_by_save.astimezone(datetime.timezone.utc)
    read_in_another_zone = read_from_database.astimezone(datetime.timezone(datetime.timedelta(hours=5)))

    assert written_by_save.tzinfo is None
    for read_back in (read_from_database, read_in_another_zone, written_by_save):
        row = _row(last_synced=read_back)
        assert save_seen_on_row(row, _saved_kb(last_synced=written_by_save)) == OWN_SAVE
        assert save_seen_on_row(row, _saved_kb(last_synced=read_from_database)) == OWN_SAVE


def test_an_older_and_a_newer_row_are_told_apart_whatever_their_time_zone():
    saved_at = indexing_started_fields()["last_synced"]
    read_back = saved_at.astimezone(datetime.timezone.utc)
    one_second = datetime.timedelta(seconds=1)
    started_kb = _saved_kb(last_synced=saved_at)

    assert save_seen_on_row(_row(last_synced=read_back + one_second), started_kb) == NEWER_SAVE
    assert save_seen_on_row(_row(last_synced=read_back - one_second), started_kb) == SAVE_NOT_VISIBLE
    assert save_seen_on_row(_row(last_synced=None), started_kb) == SAVE_NOT_VISIBLE
    assert save_seen_on_row(None, started_kb) == SAVE_NOT_VISIBLE


@pytest.mark.asyncio
async def test_status_goes_from_failed_to_indexing_to_success_on_a_new_save():
    failed_yesterday = SAVED_AT - datetime.timedelta(days=1)
    row = _row(last_sync_status="error", last_sync_error="old failure", last_synced=failed_yesterday)
    resaved = KBBase(name="Acme help centre", type="text", content="Acme help text", last_sync_status="error")

    mark_indexing_started(resaved)
    for field, value in resaved.model_dump(exclude_none=True).items():
        setattr(row, field, value)
    while_indexing = (row.last_sync_status, row.last_sync_error)
    row.last_synced = row.last_synced.astimezone(datetime.timezone.utc)
    await _record([row], started_kb=_saved_kb(last_synced=row.last_synced), status="success", message="")

    assert while_indexing == (INDEXING_STATUS, "")
    assert (row.last_sync_status, row.last_sync_error) == ("success", "")


def test_schedule_passes_the_tenant_of_the_request(monkeypatch):
    created = {}

    def create_task(coroutine):
        created["coroutine"] = coroutine
        coroutine.close()
        return MagicMock()

    index = MagicMock(return_value=AsyncMock()())
    monkeypatch.setattr(agent_knowledge_utils.asyncio, "create_task", create_task)
    monkeypatch.setattr(agent_knowledge_utils, "index_saved_knowledge_base", index)
    monkeypatch.setattr(agent_knowledge_utils, "get_tenant_context", lambda: "acme")
    kb = _saved_kb()

    agent_knowledge_utils.schedule_rag_load("rag-manager", kb, action="create")

    index.assert_called_once_with("rag-manager", kb, "create", "acme")


# ---- LEGRA finalize leaves the indexing status alone

@pytest.mark.asyncio
async def test_finalize_does_not_write_back_the_status_it_read():
    read_while_indexing = _saved_kb("file", last_sync_error="", last_successful_sync=SAVED_AT)
    knowledge_service = AsyncMock()
    knowledge_service.get_by_id = AsyncMock(return_value=read_while_indexing)
    rag_manager = SimpleNamespace(finalize_legra=AsyncMock(return_value=True))

    await route_module.finalize_legra_knowledgebase(KB_ID, knowledge_service=knowledge_service, rag_manager=rag_manager)

    written = knowledge_service.update.await_args.args[1].model_dump(exclude_none=True)
    assert written["legra_finalize"] is True
    assert written["name"] == "Acme help centre"
    assert not {"last_synced", "last_sync_status", "last_sync_error", "last_successful_sync"} & set(written)


# ---- failure paths of the loader that used to leave no trace

GUIDE_PATH = "/data/uploads/9f3a-guide.pdf"
GUIDE_FILE = {"file_path": GUIDE_PATH, "original_file_name": "Acme guide.pdf", "storage_provider": "local"}
PRICES_FILE = "/data/uploads/globex-prices.docx"


def _file_kb(files):
    return SimpleNamespace(
        id=KB_ID, type="file", name="Acme guides", description="", content="", files=files, legra_finalize=False
    )


async def _load(kb, service, extract=None):
    manager = AgentRAGServiceManager()
    extractor = SimpleNamespace(extract=extract or MagicMock(return_value="Acme help text"))
    with patch.object(manager, "get_service", new=AsyncMock(return_value=service)), patch.object(
        manager_module, "FileTextExtractor", new=lambda: extractor
    ), patch.object(manager_module, "bulk_delete_documents", new=AsyncMock(return_value={})):
        return await manager.load_knowledge_items([kb], action="update")


def _store():
    service = AsyncMock()
    service.get_document_ids = AsyncMock(return_value=[])
    service.add_document = AsyncMock(return_value={"vector": True})
    return service


@pytest.mark.asyncio
async def test_unavailable_stores_end_as_failed():
    results = await _load(_file_kb([PRICES_FILE]), service=None)

    assert results == [{"id": f"KB:{KB_ID}", "result": {}, "error": STORES_UNAVAILABLE_ERROR}]
    assert indexing_outcome(results) == (
        "error",
        f"1 of 1 documents could not be indexed: The knowledge base: {STORES_UNAVAILABLE_ERROR}",
    )


@pytest.mark.asyncio
async def test_an_unreadable_file_ends_as_failed_and_the_other_file_keeps_its_own_content(caplog):
    def extract(path):
        if path.endswith("9f3a-guide.pdf"):
            raise ValueError("cannot open /data/uploads/9f3a-guide.pdf: file is encrypted")
        return "Globex price list"

    service = _store()

    with caplog.at_level(logging.ERROR):
        results = await _load(_file_kb([GUIDE_FILE, PRICES_FILE]), service, extract=extract)

    stored = [(call.args[0], call.args[1]) for call in service.add_document.await_args_list]
    assert stored == [(f"KB:{KB_ID}#file_1:{PRICES_FILE}", "Globex price list")]
    assert indexing_outcome(results) == (
        "success_with_warnings",
        "1 of 2 documents could not be indexed: Acme guide.pdf: the file could not be read",
    )
    assert "file is encrypted" in caplog.text


@pytest.mark.asyncio
async def test_a_stored_file_keeps_the_name_it_was_uploaded_with():
    service = _store()
    service.add_document = AsyncMock(return_value={"vector": False})

    results = await _load(_file_kb([GUIDE_FILE]), service)

    assert results == [{"id": f"KB:{KB_ID}#file_0:{GUIDE_PATH}", "result": {"vector": False}, "name": "Acme guide.pdf"}]
    assert indexing_outcome(results) == (
        "error",
        "1 of 1 documents could not be indexed: Acme guide.pdf was not loaded into the knowledge base (vector)",
    )


@pytest.mark.asyncio
async def test_a_single_unreadable_file_ends_as_failed_without_paths_in_the_reason():
    missing_file = MagicMock(side_effect=OSError(f"[Errno 2] No such file or directory: '{PRICES_FILE}'"))

    results = await _load(_file_kb([PRICES_FILE]), _store(), extract=missing_file)

    assert indexing_outcome(results) == (
        "error",
        "1 of 1 documents could not be indexed: globex-prices.docx: the file could not be read",
    )


@pytest.mark.asyncio
async def test_a_file_without_a_stored_path_ends_as_failed():
    nowhere = {"storage_provider": "local", "file_id": "f-1", "original_file_name": "Acme guide.pdf"}

    results = await _load(_file_kb([nowhere]), _store())

    assert indexing_outcome(results) == (
        "error",
        f"1 of 1 documents could not be indexed: Acme guide.pdf: {FILE_NOT_STORED_ERROR}",
    )


@pytest.mark.asyncio
async def test_a_file_without_text_ends_as_failed_without_calling_the_store():
    service = _store()

    results = await _load(_file_kb(["/data/uploads/scan.pdf"]), service, extract=MagicMock(return_value="  \n"))

    service.add_document.assert_not_awaited()
    assert indexing_outcome(results) == ("error", "1 of 1 documents could not be indexed: scan.pdf: no readable text")


@pytest.mark.asyncio
async def test_a_linked_file_is_downloaded_and_a_local_one_is_read_from_disk():
    linked = {"file_url": "https://files.example.com/9f3a-guide.pdf?sig=abc", "storage_provider": "s3"}
    manager = AgentRAGServiceManager()
    download = AsyncMock(return_value="Acme guide text")
    read_from_disk = MagicMock(return_value="Globex price list")
    extractor = SimpleNamespace(extract=read_from_disk)
    service = _store()
    with patch.object(manager, "get_service", new=AsyncMock(return_value=service)), patch.object(
        manager_module, "FileTextExtractor", new=lambda: extractor
    ), patch.object(manager, "_download_url_to_temp_file", new=download), patch.object(
        manager_module, "bulk_delete_documents", new=AsyncMock(return_value={})
    ):
        await manager.load_knowledge_items([_file_kb([linked, PRICES_FILE])], action="update")

    download.assert_awaited_once_with("https://files.example.com/9f3a-guide.pdf?sig=abc", extractor, delete_file=True)
    read_from_disk.assert_called_once_with(path=PRICES_FILE)
    assert [call.args[1] for call in service.add_document.await_args_list] == ["Acme guide text", "Globex price list"]


@pytest.mark.asyncio
async def test_a_text_knowledge_base_that_is_stored_ends_as_success():
    kb = SimpleNamespace(id=KB_ID, type="text", name="Acme help centre", description="", content="Acme help text")
    service = _store()

    results = await _load(kb, service)

    assert results == [{"id": CONTENT_ID, "result": {"vector": True}}]
    assert indexing_outcome(results) == ("success", "")
