"""A document that fails to load into a knowledge base counts as an error in every sync."""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.modules.data.load_result import (
    DocumentNotLoadedError,
    KnowledgeBaseUnavailableError,
    article_sync_outcome,
    ensure_has_text,
    ensure_loaded,
    load_document,
    missed_stores_warning,
)


@pytest.mark.parametrize("result", [{"vector": True}, {"vector": True, "legra": True}, {"vector": True, "legra": False}])
def test_a_document_counts_as_loaded_when_a_store_took_it(result):
    ensure_loaded(result, "Refunds")


@pytest.mark.parametrize(
    "result, warning",
    [
        ({"vector": True}, None),
        ({"vector": True, "legra": True}, None),
        ({"vector": True, "legra": False}, "Refunds was loaded but is missing from: legra"),
        ({"vector": False, "legra": True}, "Refunds was loaded but is missing from: vector"),
    ],
)
def test_a_partly_loaded_document_gets_a_warning_naming_the_missing_stores(result, warning):
    assert missed_stores_warning(result, "Refunds") == warning


def test_failed_load_names_the_stores_that_refused_it():
    with pytest.raises(DocumentNotLoadedError, match=r"Refunds was not loaded .*\(vector, legra\)"):
        ensure_loaded({"vector": False, "legra": False}, "Refunds")


@pytest.mark.parametrize("result", [{}, None])
def test_unreachable_stores_are_reported_as_no_store_reached(result):
    with pytest.raises(KnowledgeBaseUnavailableError, match="no store reached"):
        ensure_loaded(result, "Refunds")


def test_blank_text_counts_as_not_loaded():
    with pytest.raises(DocumentNotLoadedError, match="scan.pdf has no readable text"):
        ensure_has_text("  \n ", "scan.pdf")


@pytest.mark.parametrize(
    "attempted, copied, errors, had_articles, status, message_start",
    [
        (3, 3, [], False, "success", ""),
        (3, 2, ["Error processing article 7: x"], False, "success_with_warnings", "1 of 3 articles could not be copied"),
        (2, 0, ["e1", "e2"], False, "error", "2 of 2 articles could not be copied"),
        (1, 0, ["e1"], True, "success_with_warnings", "1 of 1 articles could not be copied"),
        (0, 0, ["Error deleting article 9: x"], True, "success_with_warnings", "Error deleting article 9"),
    ],
)
def test_article_sync_outcome(attempted, copied, errors, had_articles, status, message_start):
    outcome_status, message = article_sync_outcome(attempted, copied, errors, had_articles)
    assert outcome_status == status
    assert message.startswith(message_start)


@pytest.mark.asyncio
async def test_partly_loaded_document_is_kept_and_reported():
    rag_manager = MagicMock()
    rag_manager.add_document = AsyncMock(return_value={"vector": True, "legra": False})
    rag_manager.delete_document = AsyncMock()

    warning = await load_document(rag_manager, "kb", "KB:1#a.txt", "text", {}, "a.txt")

    assert warning == "a.txt was loaded but is missing from: legra"
    rag_manager.delete_document.assert_not_awaited()


def _s3_output_kb(rag_config=None):
    from app.schemas.agent_knowledge import KBRead

    return KBRead(
        id=uuid.uuid4(),
        name="S3 KB",
        type="s3",
        sync_source_id=uuid.uuid4(),
        extra_metadata={"save_output": True, "save_output_path": "output/", "processing_mode": "none"},
        rag_config=rag_config or {"vector": {"enabled": True}},
    )


async def _run_s3_output_sync(
    load_results, contents_by_name=None, store_available=True, download_errors=(), rag_config=None, move_error=None
):
    from app.tasks import kb_batch_tasks

    kb = _s3_output_kb(rag_config)
    kb_service = MagicMock()
    kb_service.get_by_id = AsyncMock(return_value=kb)
    ds_service = MagicMock()
    ds_service.get_by_id = AsyncMock(
        return_value=SimpleNamespace(source_type="s3", name="S3 DS", connection_data={"bucket_name": "acme"})
    )
    rag_manager = MagicMock()
    if store_available:
        rag_manager.add_document = AsyncMock(side_effect=lambda _kb, doc_id, *_, **__: load_results[doc_id.rsplit("/", 1)[-1]])
    else:
        rag_manager.add_document = AsyncMock(return_value={})
    rag_manager.delete_document = AsyncMock(return_value={"vector": True})
    services = {
        kb_batch_tasks.KnowledgeBaseService: kb_service,
        kb_batch_tasks.DataSourceService: ds_service,
        kb_batch_tasks.AgentRAGServiceManager: rag_manager,
    }
    files = [{"key": f"in/{name}", "size": 5} for name in load_results]
    contents_by_name = contents_by_name or {}

    def download(**kwargs):
        name = kwargs["item"].rsplit("/", 1)[-1]
        if name in download_errors:
            raise RuntimeError("connection reset")
        return name.encode()

    def extract(mode, file):
        name = file.decode()
        return {"content": contents_by_name.get(name, "text"), "file_name": name, "metadata": {}}

    move = AsyncMock(side_effect=move_error)

    with patch.object(kb_batch_tasks, "injector") as fake_injector, patch.object(
        kb_batch_tasks, "s3_list_source", AsyncMock(return_value={"files": files})
    ), patch.object(kb_batch_tasks, "s3_download_file", AsyncMock(side_effect=download)), patch.object(
        kb_batch_tasks, "get_content_from_file", AsyncMock(side_effect=extract)
    ), patch.object(kb_batch_tasks, "s3_move_file", move):
        fake_injector.get.side_effect = lambda dependency: services.get(dependency, MagicMock())
        result = await kb_batch_tasks.batch_process_files_kb_async(kb_id=str(kb.id))
    moved = [call.kwargs["item"] for call in move.await_args_list]
    return result, moved, rag_manager


@pytest.mark.asyncio
async def test_s3_file_that_failed_to_load_stays_in_the_input_folder():
    result, moved, _ = await _run_s3_output_sync({"a.txt": {"vector": True}, "b.txt": {"vector": False}})

    assert moved == ["in/a.txt"]
    assert result["processed_kbs"] == 1
    assert result["failed_kb"] == 1
    assert result["status"] == "error"
    assert result["message"].startswith("1 file(s) could not be loaded")


@pytest.mark.asyncio
async def test_s3_files_after_a_failed_one_are_still_processed():
    result, moved, _ = await _run_s3_output_sync({"a.txt": {"vector": False}, "b.txt": {"vector": True}})

    assert moved == ["in/b.txt"]
    assert result["processed_kbs"] == 1
    assert result["failed_kb"] == 1
    assert result["status"] == "error"


class _RecordedRun:
    """Keeps the outcome Sync Now saves for the page."""

    def __init__(self):
        self.outcome = None

    async def finish(self, tenant_id, kb_id, run_id, **outcome):
        self.outcome = outcome
        return True


async def _sync_now_outcome(batch_result):
    from app.tasks import kb_manual_sync

    run = _RecordedRun()
    await kb_manual_sync._record_outcome(run, "master", "kb-1", "run-1", {"status": "success", "result": batch_result})
    return run.outcome


@pytest.mark.asyncio
async def test_sync_now_reports_the_error_when_a_file_was_not_loaded():
    batch_result = {"status": "error", "message": "1 file(s) could not be loaded", "failed_kb": 1}

    outcome = await _sync_now_outcome(batch_result)

    assert outcome["status"] == "failed"
    assert outcome["error"] == "1 file(s) could not be loaded"


@pytest.mark.asyncio
async def test_sync_now_reports_completed_when_every_file_loaded():
    outcome = await _sync_now_outcome({"failed_kb": 0})

    assert outcome["status"] == "succeeded"
    assert outcome["result"]["status"] == "completed"


@pytest.mark.asyncio
async def test_s3_files_that_loaded_are_moved_as_before():
    result, moved, rag_manager = await _run_s3_output_sync({"a.txt": {"vector": True}, "b.txt": {"vector": True}})

    assert moved == ["in/a.txt", "in/b.txt"]
    assert result["processed_kbs"] == 2
    assert result["failed_kb"] == 0
    assert "status" not in result
    assert all(call.kwargs["legra_finalize"] is True for call in rag_manager.add_document.await_args_list)


@pytest.mark.asyncio
async def test_s3_output_folder_only_moves_files_of_a_knowledge_base_without_the_vector_store():
    result, moved, rag_manager = await _run_s3_output_sync(
        {"a.txt": {"legra": True}}, rag_config={"vector": {"enabled": False}, "legra": {"enabled": True}}
    )

    assert moved == ["in/a.txt"]
    assert result["processed_kbs"] == 1
    assert result["failed_kb"] == 0
    rag_manager.add_document.assert_not_awaited()


@pytest.mark.asyncio
async def test_s3_output_folder_moves_a_partly_loaded_file_as_before():
    result, moved, _ = await _run_s3_output_sync({"a.txt": {"vector": True, "legra": False}})

    assert moved == ["in/a.txt"]
    assert result["processed_kbs"] == 1
    assert result["failed_kb"] == 0
    assert "status" not in result


@pytest.mark.asyncio
async def test_s3_file_without_readable_text_is_moved_but_not_counted_as_processed():
    result, moved, rag_manager = await _run_s3_output_sync(
        {"a.txt": {"vector": True}, "blank.txt": {"vector": False}}, contents_by_name={"blank.txt": "  \n "}
    )

    assert moved == ["in/a.txt", "in/blank.txt"]
    assert result["processed_kbs"] == 1
    assert result["skipped_kbs"] == 1
    assert result["failed_kb"] == 0
    assert rag_manager.add_document.await_count == 1


@pytest.mark.asyncio
async def test_s3_file_that_cannot_be_downloaded_stops_the_run_as_before():
    with pytest.raises(RuntimeError, match="connection reset"):
        await _run_s3_output_sync({"a.txt": {"vector": True}, "b.txt": {"vector": True}}, download_errors={"a.txt"})


@pytest.mark.asyncio
async def test_s3_file_that_cannot_be_moved_stops_the_run_as_before():
    with pytest.raises(PermissionError, match="access denied"):
        await _run_s3_output_sync({"a.txt": {"vector": True}}, move_error=PermissionError("access denied"))


@pytest.mark.asyncio
async def test_s3_output_sync_stops_when_the_stores_cannot_be_reached():
    with pytest.raises(KnowledgeBaseUnavailableError):
        await _run_s3_output_sync({"a.txt": {"vector": True}}, store_available=False)


def _scheduled_kb(kb_type, **fields):
    from app.schemas.agent_knowledge import KBRead

    return KBRead(
        id=uuid.uuid4(), name=f"{kb_type} KB", type=kb_type, sync_source_id=uuid.uuid4(),
        sync_schedule="* * * * *", sync_active=True, rag_config={}, extra_metadata={}, **fields,
    )


def _file_sync_rag_manager(load_results):
    rag_manager = MagicMock()
    rag_manager.get_document_ids = AsyncMock(return_value=[])
    rag_manager.add_document = AsyncMock(side_effect=lambda kb, doc_id, *_, **__: load_results[doc_id.rsplit("/", 1)[-1]])
    rag_manager.delete_document = AsyncMock(return_value={"vector": True})
    return rag_manager


async def _run_s3_scheduled_sync(files, load_results, knowledge_bases=None, rag_manager=None):
    from app.tasks import s3_tasks

    kb = _scheduled_kb("s3")
    kb_service = MagicMock()
    kb_service.get_by_id = AsyncMock(return_value=kb)
    kb_service.get_all = AsyncMock(return_value=knowledge_bases)
    kb_service.update = AsyncMock()
    ds_service = MagicMock()
    ds_service.get_by_id = AsyncMock(return_value=SimpleNamespace(
        name="S3 DS", source_type="s3",
        connection_data={"prefix": "in/", "bucket_name": "acme", "access_key": "k", "secret_key": "s", "region": "us-east-1"},
    ))
    rag_manager = rag_manager or _file_sync_rag_manager(load_results)

    class FakeS3Client:
        def __init__(self, **_):
            pass

        def list_files(self, prefix=None):
            return {"files": [
                {"key": key, "size": len(text), "last_modified": "2026-11-07T00:00:00+0000"} for key, text in files.items()
            ]}

        def download_file(self, key, local_path):
            with open(local_path, "w") as f:
                f.write(files[key])
            return True

    services = {s3_tasks.KnowledgeBaseService: kb_service, s3_tasks.DataSourceService: ds_service, s3_tasks.AgentRAGServiceManager: rag_manager}
    with patch.object(s3_tasks, "injector") as fake_injector, patch.object(s3_tasks, "S3Client", FakeS3Client):
        fake_injector.get.side_effect = lambda dependency: services[dependency]
        return await s3_tasks.import_s3_files_to_kb_async(kb_id=None if knowledge_bases else kb.id)


@pytest.mark.asyncio
async def test_s3_scheduled_sync_reports_a_failed_load_as_an_error():
    result = await _run_s3_scheduled_sync(
        {"in/a.txt": "refund policy", "in/b.txt": "parking zones"},
        {"a.txt": {"vector": True}, "b.txt": {"vector": False}},
    )

    assert result["files_added"] == 1
    assert len(result["errors"]) == 1
    assert "b.txt was not loaded into the knowledge base" in result["errors"][0]


@pytest.mark.asyncio
async def test_s3_scheduled_sync_counts_a_partly_loaded_file_and_warns_about_it():
    result = await _run_s3_scheduled_sync({"in/a.txt": "refund policy"}, {"a.txt": {"vector": True, "legra": False}})

    assert result["files_added"] == 1
    assert result["errors"] == ["a.txt was loaded but is missing from: legra"]


@pytest.mark.asyncio
async def test_s3_scheduled_sync_keeps_the_errors_of_every_knowledge_base():
    failing_kb, healthy_kb = _scheduled_kb("s3"), _scheduled_kb("s3")
    rag_manager = _file_sync_rag_manager({})
    rag_manager.add_document = AsyncMock(side_effect=lambda kb, *_, **__: {"vector": kb.id != failing_kb.id})

    result = await _run_s3_scheduled_sync(
        {"in/a.txt": "refund policy"}, {}, knowledge_bases=[failing_kb, healthy_kb], rag_manager=rag_manager
    )

    assert result["files_added"] == 1
    assert len(result["errors"]) == 1
    assert "a.txt was not loaded into the knowledge base" in result["errors"][0]


@pytest.mark.asyncio
async def test_s3_scheduled_sync_reports_a_file_without_readable_text_as_an_error():
    result = await _run_s3_scheduled_sync({"in/blank.txt": "  \n "}, {"blank.txt": {"vector": False}})

    assert result["files_added"] == 0
    assert "blank.txt has no readable text" in result["errors"][0]


@pytest.mark.asyncio
async def test_s3_scheduled_sync_skips_empty_objects_such_as_folders():
    result = await _run_s3_scheduled_sync({"in/": "", "in/a.txt": "refund policy"}, {"a.txt": {"vector": True}})

    assert result["files_added"] == 1
    assert result["errors"] is None


async def _run_sharepoint_sync(files, load_results):
    from app.tasks import sharepoint_tasks

    kb = _scheduled_kb("sharepoint", urls=["https://acme.sharepoint.com/sites/help"])
    kb_service = MagicMock()
    kb_service.get_by_id = AsyncMock(return_value=kb)
    kb_service.update = AsyncMock()
    ds_service = MagicMock()
    ds_service.get_by_id = AsyncMock(return_value=SimpleNamespace(source_type="o365", connection_data={"app_settings_id": str(uuid.uuid4()), "refresh_token": "r", "redirect_uri": "https://acme.example/cb"}))
    app_settings_service = MagicMock()
    app_settings_service.get_by_id = AsyncMock(return_value=SimpleNamespace(
        values={"microsoft_client_id": "c", "microsoft_client_secret": "s", "microsoft_tenant_id": "t"}
    ))
    rag_manager = _file_sync_rag_manager(load_results)
    connector = MagicMock()
    connector.list_files = AsyncMock(return_value={"files": [
        {"path": f"/docs/{name}", "name": name, "download_url": name} for name in files
    ]})
    connector.get_file_content = AsyncMock(side_effect=lambda url: files[url].encode())

    services = {
        sharepoint_tasks.KnowledgeBaseService: kb_service,
        sharepoint_tasks.DataSourceService: ds_service,
        sharepoint_tasks.AppSettingsService: app_settings_service,
        sharepoint_tasks.AgentRAGServiceManager: rag_manager,
    }
    with patch.object(sharepoint_tasks, "injector") as fake_injector, patch.object(
        sharepoint_tasks, "Office365Connector", return_value=connector
    ), patch.object(sharepoint_tasks, "decrypt_key", side_effect=lambda value: value):
        fake_injector.get.side_effect = lambda dependency: services[dependency]
        result = await sharepoint_tasks.import_sharepoint_files_to_kb_async(kb_id=kb.id)
    return result, rag_manager


@pytest.mark.asyncio
async def test_sharepoint_sync_reports_a_failed_load_as_an_error():
    result, _ = await _run_sharepoint_sync(
        {"a.txt": "refund policy", "b.txt": "parking zones"},
        {"a.txt": {"vector": True}, "b.txt": {"vector": False}},
    )

    assert result["files_added"] == 1
    assert any("b.txt was not loaded into the knowledge base" in error for error in result["errors"])


@pytest.mark.asyncio
async def test_sharepoint_sync_reports_a_file_without_readable_text_as_an_error():
    result, _ = await _run_sharepoint_sync({"blank.txt": "  \n "}, {"blank.txt": {"vector": False}})

    assert result["files_added"] == 0
    assert any("blank.txt has no readable text" in error for error in result["errors"])


@pytest.mark.asyncio
async def test_sharepoint_sync_skips_an_empty_file_without_an_error():
    result, _ = await _run_sharepoint_sync({"empty.txt": ""}, {})

    assert result["files_added"] == 0
    assert not result["errors"]


@pytest.mark.asyncio
async def test_sharepoint_sync_counts_a_partly_loaded_file_and_warns_about_it():
    result, rag_manager = await _run_sharepoint_sync({"a.txt": "refund policy"}, {"a.txt": {"vector": True, "legra": False}})

    assert result["files_added"] == 1
    assert "a.txt was loaded but is missing from: legra" in result["errors"]
    rag_manager.delete_document.assert_not_awaited()
