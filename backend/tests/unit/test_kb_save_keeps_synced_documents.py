"""Saving or creating a knowledge base leaves the documents of synced types to their sync."""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

import app.api.v1.routes.agent_knowledge as route_module
import app.modules.data.manager as manager_module
from app.modules.data.manager import AgentRAGServiceManager, save_load_action
from app.schemas.agent_knowledge import KBBase, KBRead

ARTICLE_SYNC_TYPES = ["zendesk", "salesforce"]
FILE_SYNC_TYPES = ["s3", "sharepoint", "smb_share_folder", "azure_blob", "google_bucket"]
SYNCED_TYPES = ARTICLE_SYNC_TYPES + FILE_SYNC_TYPES
REBUILT_TYPES = ["text", "file", "url", "database"]
RAG_CONFIG = {"enabled": True, "vector": {"enabled": True, "chunk_size": 1000}}
CHANGED_RAG_CONFIG = {"enabled": True, "vector": {"enabled": True, "chunk_size": 500}}
SOURCE_ID = uuid.uuid4()
SITE_URLS = ["https://acme.sharepoint.com/sites/help"]


def _kb(kb_type, rag_config=None, sync_source_id=SOURCE_ID, urls=SITE_URLS):
    return SimpleNamespace(type=kb_type, rag_config=rag_config, sync_source_id=sync_source_id, urls=urls)


async def _load(kb_type, action, existing_ids):
    kb = KBRead(id=uuid.uuid4(), name="KB", type=kb_type, content="Acme help text", extra_metadata={})
    service = AsyncMock()
    service.get_document_ids = AsyncMock(return_value=list(existing_ids))
    service.add_document = AsyncMock(return_value={"vector": True})
    bulk_delete = AsyncMock(return_value={})
    manager = AgentRAGServiceManager()
    with patch.object(manager, "get_service", new=AsyncMock(return_value=service)) as get_service, patch.object(
        manager_module, "bulk_delete_documents", new=bulk_delete
    ):
        await manager.load_knowledge_items([kb], action=action)
    return get_service, service, bulk_delete


@pytest.mark.asyncio
@pytest.mark.parametrize("kb_type", SYNCED_TYPES)
@pytest.mark.parametrize("action", ["update", "create"])
async def test_synced_types_keep_their_documents(kb_type, action):
    get_service, service, bulk_delete = await _load(kb_type, action, ["KB:x#file_a", "KB:x#file_b"])

    get_service.assert_not_awaited()
    bulk_delete.assert_not_awaited()
    service.add_document.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("kb_type", REBUILT_TYPES)
async def test_saving_other_types_still_rebuilds_them(kb_type):
    with patch("app.core.utils.bi_utils.set_url_content_if_has_rag", new=AsyncMock()):
        _, service, bulk_delete = await _load(kb_type, "update", ["KB:x#content"])

    bulk_delete.assert_awaited_once()
    service.add_document.assert_awaited_once()


async def _clear(remaining_ids):
    kb = KBRead(id=uuid.uuid4(), name="KB", type="s3", extra_metadata={})
    service = AsyncMock()
    service.get_document_ids = AsyncMock(return_value=remaining_ids)
    bulk_delete = AsyncMock(return_value={})
    manager = AgentRAGServiceManager()
    with patch.object(manager, "get_service", new=AsyncMock(return_value=service)), patch.object(
        manager_module, "bulk_delete_documents", new=bulk_delete
    ):
        await manager.clear_documents(kb)
    return kb, service, bulk_delete


@pytest.mark.asyncio
async def test_clear_deletes_every_document_of_the_kb_at_once():
    kb, service, bulk_delete = await _clear([])

    service.delete_by_metadata.assert_awaited_once_with({"kb_id": str(kb.id)})
    bulk_delete.assert_not_awaited()
    service.add_document.assert_not_awaited()


@pytest.mark.asyncio
async def test_clear_also_removes_documents_of_stores_without_a_bulk_delete():
    _, service, bulk_delete = await _clear(["KB:x#content"])

    bulk_delete.assert_awaited_once_with(service, ["KB:x#content"])


@pytest.mark.asyncio
@pytest.mark.parametrize("get_service", [AsyncMock(return_value=None), AsyncMock(side_effect=RuntimeError("store down"))])
async def test_a_failed_clear_does_not_fail_the_save(get_service):
    kb = KBRead(id=uuid.uuid4(), name="KB", type="s3", extra_metadata={})
    manager = AgentRAGServiceManager()
    with patch.object(manager, "get_service", new=get_service):
        await manager.clear_documents(kb)


@pytest.mark.parametrize("kb_type", SYNCED_TYPES)
def test_plain_save_keeps_synced_documents(kb_type):
    assert save_load_action(_kb(kb_type, RAG_CONFIG), _kb(kb_type, RAG_CONFIG)) == "update"


@pytest.mark.parametrize("kb_type", SYNCED_TYPES)
def test_save_without_rag_config_keeps_synced_documents(kb_type):
    assert save_load_action(_kb(kb_type, RAG_CONFIG), _kb(kb_type, None)) == "update"


@pytest.mark.parametrize("kb_type", FILE_SYNC_TYPES)
def test_rag_config_change_clears_file_synced_documents(kb_type):
    assert save_load_action(_kb(kb_type, RAG_CONFIG), _kb(kb_type, CHANGED_RAG_CONFIG)) == "clear"


@pytest.mark.parametrize(
    "stored, incoming",
    [
        ({"enabled": True, "vector": {"enabled": True}}, RAG_CONFIG),
        (RAG_CONFIG, {**RAG_CONFIG, "legra": {"enabled": False, "graph_n_neighbors": 10}}),
        (
            {"enabled": True, "vector": {"enabled": True, "embedding_type": "huggingface"}},
            {"enabled": True, "vector": {"enabled": True, "embedding_type": "huggingface", "embedding_batch_size": 32}},
        ),
        ({"enabled": True, "vector": {"enabled": True, "chunk_size": 1000, "chunk_overlap": 200}}, RAG_CONFIG),
        (None, {}),
        (RAG_CONFIG, {"enabled": True, "vector": {**RAG_CONFIG["vector"], "vector_db_host": "localhost", "vector_db_port": 5432}}),
        (
            {"enabled": True, "vector": {"enabled": True, "embedding_type": "huggingface"}},
            {"enabled": True, "vector": {"enabled": True, "embedding_type": "huggingface", "embedding_batch_size": 64}},
        ),
        (
            {**RAG_CONFIG, "legra": {"enabled": True}},
            {**RAG_CONFIG, "legra": {"enabled": True, "generation_model": "acme-writer", "generation_max_tokens": 64}},
        ),
        (RAG_CONFIG, {"enabled": True, "vector": {"enabled": True, "chunk_size": 100, "chunk_overlap": 500}}),
    ],
)
def test_settings_that_leave_the_stored_content_unchanged_keep_file_synced_documents(stored, incoming):
    assert save_load_action(_kb("s3", stored), _kb("s3", incoming)) == "update"


@pytest.mark.parametrize(
    "stored, incoming",
    [
        ({"enabled": True, "vector": {"enabled": True}}, CHANGED_RAG_CONFIG),
        (RAG_CONFIG, {**RAG_CONFIG, "legra": {"enabled": True}}),
        (RAG_CONFIG, {"enabled": True, "vector": {"enabled": True, "chunk_size": 1000, "embedding_type": "huggingface"}}),
        (RAG_CONFIG, {"enabled": True, "vector": {**RAG_CONFIG["vector"], "vector_db_collection_name": "globex"}}),
        (
            {"enabled": True, "vector": {"enabled": True, "vector_db_type": "qdrant", "vector_db_port": 6333}},
            {"enabled": True, "vector": {"enabled": True, "vector_db_type": "qdrant", "vector_db_port": 6334}},
        ),
        ({"vector": {"enabled": True}}, {"enabled": True, "vector": {"enabled": True}}),
    ],
)
def test_settings_that_change_the_stored_content_clear_file_synced_documents(stored, incoming):
    assert save_load_action(_kb("s3", stored), _kb("s3", incoming)) == "clear"


@pytest.mark.parametrize("kb_type", FILE_SYNC_TYPES)
def test_data_source_change_clears_file_synced_documents(kb_type):
    assert save_load_action(_kb(kb_type, RAG_CONFIG), _kb(kb_type, RAG_CONFIG, uuid.uuid4())) == "clear"


@pytest.mark.parametrize("kb_type", FILE_SYNC_TYPES)
def test_save_without_data_source_keeps_file_synced_documents(kb_type):
    assert save_load_action(_kb(kb_type, RAG_CONFIG), _kb(kb_type, RAG_CONFIG, None)) == "update"


def test_sharepoint_site_change_clears_documents():
    other_site = ["https://acme.sharepoint.com/sites/billing"]

    assert save_load_action(_kb("sharepoint", RAG_CONFIG), _kb("sharepoint", RAG_CONFIG, urls=other_site)) == "clear"


@pytest.mark.parametrize(
    "kb_type, incoming_urls",
    [("sharepoint", None), ("sharepoint", SITE_URLS + ["https://acme.sharepoint.com/sites/billing"]), ("s3", ["https://globex.example.com/x"])],
)
def test_urls_that_are_not_a_new_site_keep_documents(kb_type, incoming_urls):
    assert save_load_action(_kb(kb_type, RAG_CONFIG), _kb(kb_type, RAG_CONFIG, urls=incoming_urls)) == "update"


@pytest.mark.parametrize("kb_type", ARTICLE_SYNC_TYPES)
def test_data_source_change_keeps_article_synced_documents(kb_type):
    assert save_load_action(_kb(kb_type, RAG_CONFIG), _kb(kb_type, RAG_CONFIG, uuid.uuid4())) == "update"


@pytest.mark.parametrize("kb_type", ARTICLE_SYNC_TYPES)
def test_rag_config_change_keeps_article_synced_documents(kb_type):
    assert save_load_action(_kb(kb_type, RAG_CONFIG), _kb(kb_type, CHANGED_RAG_CONFIG)) == "update"


@pytest.mark.parametrize("kb_type", SYNCED_TYPES)
@pytest.mark.parametrize("previous_type", ["text", "file", "url"])
def test_changing_type_to_a_synced_type_clears_old_documents(previous_type, kb_type):
    assert save_load_action(_kb(previous_type, RAG_CONFIG), _kb(kb_type, RAG_CONFIG)) == "clear"


@pytest.mark.parametrize("previous_type, kb_type", [("zendesk", "s3"), ("s3", "sharepoint"), ("salesforce", "zendesk")])
def test_changing_between_synced_types_clears_old_documents(previous_type, kb_type):
    assert save_load_action(_kb(previous_type, RAG_CONFIG), _kb(kb_type, RAG_CONFIG)) == "clear"


@pytest.mark.parametrize("previous_type", SYNCED_TYPES)
@pytest.mark.parametrize("kb_type", REBUILT_TYPES)
def test_other_types_always_use_the_rebuild(previous_type, kb_type):
    assert save_load_action(_kb(previous_type, RAG_CONFIG), _kb(kb_type, CHANGED_RAG_CONFIG)) == "update"


async def _save_through_route(current, incoming, saved):
    knowledge_service = AsyncMock()
    knowledge_service.get_by_id = AsyncMock(return_value=current)
    knowledge_service.update = AsyncMock(return_value=saved)
    locked_read = MagicMock()
    locked_read.scalars.return_value.first.return_value = current
    knowledge_service.repository.db.execute = AsyncMock(return_value=locked_read)
    rag_manager = AsyncMock()
    with patch.object(route_module, "schedule_rag_load") as schedule, patch.object(
        route_module, "populate_remote_file_metadata", new=AsyncMock()
    ), patch.object(route_module, "set_url_content_if_no_rag", new=AsyncMock()):
        await route_module.update_knowledge_item(
            current.id, incoming, knowledge_service=knowledge_service, rag_manager=rag_manager, file_manager_service=AsyncMock()
        )
    return schedule, rag_manager


def _route_kbs(current_type, incoming_type, incoming_rag_config, sync_source_id=None):
    kb_id = uuid.uuid4()
    current = KBRead(id=kb_id, name="KB", type=current_type, rag_config=RAG_CONFIG, sync_source_id=SOURCE_ID, extra_metadata={})
    incoming = KBBase(name="KB", type=incoming_type, rag_config=incoming_rag_config, sync_source_id=sync_source_id, extra_metadata={})
    saved = KBRead(id=kb_id, name="KB", type=incoming_type, rag_config=incoming_rag_config, extra_metadata={})
    return current, incoming, saved


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "current_type, incoming_type, incoming_rag_config",
    [("s3", "s3", RAG_CONFIG), ("zendesk", "zendesk", CHANGED_RAG_CONFIG), ("text", "text", CHANGED_RAG_CONFIG)],
)
async def test_update_route_keeps_content_when_nothing_outdates_it(current_type, incoming_type, incoming_rag_config):
    current, incoming, saved = _route_kbs(current_type, incoming_type, incoming_rag_config)

    schedule, rag_manager = await _save_through_route(current, incoming, saved)

    rag_manager.clear_documents.assert_not_awaited()
    schedule.assert_called_once_with(rag_manager, saved, action="update")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "current_type, incoming_type, incoming_rag_config",
    [("s3", "s3", CHANGED_RAG_CONFIG), ("text", "salesforce", RAG_CONFIG), ("zendesk", "s3", RAG_CONFIG)],
)
async def test_update_route_clears_with_the_previous_settings_before_responding(current_type, incoming_type, incoming_rag_config):
    current, incoming, saved = _route_kbs(current_type, incoming_type, incoming_rag_config)

    schedule, rag_manager = await _save_through_route(current, incoming, saved)

    rag_manager.clear_documents.assert_awaited_once_with(current)
    assert rag_manager.mock_calls.index(call.clear_documents(current)) < rag_manager.mock_calls.index(
        call.cleanup_service(str(current.id))
    )
    schedule.assert_called_once_with(rag_manager, saved, action="update")


@pytest.mark.asyncio
async def test_update_route_matches_the_data_source_sent_as_text():
    current, incoming, saved = _route_kbs("s3", "s3", RAG_CONFIG, sync_source_id=str(SOURCE_ID).upper())

    schedule, rag_manager = await _save_through_route(current, incoming, saved)

    rag_manager.clear_documents.assert_not_awaited()


def _cached_kb(kb_id, rag_config):
    return KBRead(id=kb_id, name="KB", type="s3", rag_config=rag_config, extra_metadata={})


@pytest.fixture
def built_services():
    built = []

    async def initialize(service):
        service._initialized = True
        built.append(service)
        return True

    with patch.object(manager_module.AgentRAGService, "initialize", new=initialize):
        yield built


@pytest.mark.asyncio
async def test_a_process_holding_old_settings_rebuilds_after_a_save_elsewhere(built_services):
    kb_id = uuid.uuid4()
    other_process = AgentRAGServiceManager()
    old_service = await other_process.get_service(_cached_kb(kb_id, RAG_CONFIG))

    new_service = await other_process.get_service(_cached_kb(kb_id, CHANGED_RAG_CONFIG))

    assert new_service is not old_service
    assert new_service.config.vector_config.chunking.chunk_size == 500
    assert len(built_services) == 2


@pytest.mark.asyncio
async def test_unchanged_settings_reuse_the_cached_service(built_services):
    kb_id = uuid.uuid4()
    manager = AgentRAGServiceManager()
    first = await manager.get_service(_cached_kb(kb_id, RAG_CONFIG))

    again = await manager.get_service(_cached_kb(kb_id, {"enabled": True, "vector": {"enabled": True, "chunk_size": 1000}}))

    assert again is first
    assert len(built_services) == 1


@pytest.mark.asyncio
async def test_unreadable_settings_keep_the_cached_service(built_services):
    kb_id = uuid.uuid4()
    manager = AgentRAGServiceManager()
    first = await manager.get_service(_cached_kb(kb_id, RAG_CONFIG))

    again = await manager.get_service(_cached_kb(kb_id, {"enabled": True, "vector": {"enabled": True, "chunk_size": "abc"}}))

    assert again is first
    assert len(built_services) == 1
