"""Saving or creating a knowledge base leaves the documents of synced types to their sync."""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

import app.api.v1.routes.agent_knowledge as route_module
import app.modules.data.manager as manager_module
from app.modules.data.manager import AgentRAGServiceManager, save_load_action
from app.schemas.agent_knowledge import KBBase, KBRead

ARTICLE_SYNC_TYPES = ["zendesk", "salesforce"]
FILE_SYNC_TYPES = ["s3", "sharepoint", "smb_share_folder", "azure_blob", "google_bucket"]
SYNCED_TYPES = ARTICLE_SYNC_TYPES + FILE_SYNC_TYPES
REBUILT_TYPES = ["text", "url", "database"]
RAG_CONFIG = {"vector": {"enabled": True, "chunk_size": 1000}}
CHANGED_RAG_CONFIG = {"vector": {"enabled": True, "chunk_size": 500}}


SOURCE_ID = uuid.uuid4()


def _kb(kb_type, rag_config=None, sync_source_id=SOURCE_ID):
    return SimpleNamespace(type=kb_type, rag_config=rag_config, sync_source_id=sync_source_id)


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
@pytest.mark.parametrize("kb_type", SYNCED_TYPES)
async def test_clear_removes_synced_documents_without_adding_content(kb_type):
    _, service, bulk_delete = await _load(kb_type, "clear", ["KB:x#content", "KB:x#file_a"])

    bulk_delete.assert_awaited_once_with(service, ["KB:x#content", "KB:x#file_a"])
    service.add_document.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("kb_type", REBUILT_TYPES)
async def test_saving_other_types_still_rebuilds_them(kb_type):
    with patch("app.core.utils.bi_utils.set_url_content_if_has_rag", new=AsyncMock()):
        _, service, bulk_delete = await _load(kb_type, "update", ["KB:x#content"])

    bulk_delete.assert_awaited_once()
    service.add_document.assert_awaited_once()


@pytest.mark.parametrize("kb_type", SYNCED_TYPES)
def test_plain_save_keeps_synced_documents(kb_type):
    assert save_load_action(_kb(kb_type, RAG_CONFIG), _kb(kb_type, RAG_CONFIG)) == "update"


@pytest.mark.parametrize("kb_type", SYNCED_TYPES)
def test_save_without_rag_config_keeps_synced_documents(kb_type):
    assert save_load_action(_kb(kb_type, RAG_CONFIG), _kb(kb_type, None)) == "update"


@pytest.mark.parametrize("kb_type", FILE_SYNC_TYPES)
def test_settings_added_by_the_form_keep_file_synced_documents(kb_type):
    filled_in = {"enabled": True, "vector": {**RAG_CONFIG["vector"], "embedding_region_name": "ca-central-1"}}

    assert save_load_action(_kb(kb_type, RAG_CONFIG), _kb(kb_type, filled_in)) == "update"


@pytest.mark.parametrize("kb_type", FILE_SYNC_TYPES)
def test_rag_config_change_clears_file_synced_documents(kb_type):
    assert save_load_action(_kb(kb_type, RAG_CONFIG), _kb(kb_type, CHANGED_RAG_CONFIG)) == "clear"


@pytest.mark.parametrize("kb_type", FILE_SYNC_TYPES)
def test_data_source_change_clears_file_synced_documents(kb_type):
    assert save_load_action(_kb(kb_type, RAG_CONFIG), _kb(kb_type, RAG_CONFIG, uuid.uuid4())) == "clear"


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


@pytest.mark.parametrize("previous_type", SYNCED_TYPES)
@pytest.mark.parametrize("kb_type", REBUILT_TYPES)
def test_other_types_always_use_the_rebuild(previous_type, kb_type):
    assert save_load_action(_kb(previous_type, RAG_CONFIG), _kb(kb_type, CHANGED_RAG_CONFIG)) == "update"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "current_type, incoming_type, incoming_rag_config, expected_action",
    [
        ("s3", "s3", RAG_CONFIG, "update"),
        ("s3", "s3", CHANGED_RAG_CONFIG, "clear"),
        ("text", "salesforce", RAG_CONFIG, "clear"),
        ("zendesk", "zendesk", CHANGED_RAG_CONFIG, "update"),
        ("text", "text", CHANGED_RAG_CONFIG, "update"),
    ],
)
async def test_update_route_schedules_the_save_action(current_type, incoming_type, incoming_rag_config, expected_action):
    item_id = uuid.uuid4()
    current = KBRead(id=item_id, name="KB", type=current_type, rag_config=RAG_CONFIG, extra_metadata={})
    incoming = KBBase(name="KB", type=incoming_type, rag_config=incoming_rag_config, extra_metadata={})
    knowledge_service = AsyncMock()
    knowledge_service.get_by_id = AsyncMock(return_value=current)
    knowledge_service.update = AsyncMock(return_value=current)
    rag_manager = AsyncMock()

    with patch.object(route_module, "schedule_rag_load") as schedule, patch.object(
        route_module, "populate_remote_file_metadata", new=AsyncMock()
    ), patch.object(route_module, "set_url_content_if_no_rag", new=AsyncMock()):
        await route_module.update_knowledge_item(
            item_id, incoming, knowledge_service=knowledge_service, rag_manager=rag_manager, file_manager_service=AsyncMock()
        )

    schedule.assert_called_once_with(rag_manager, current, action=expected_action)
