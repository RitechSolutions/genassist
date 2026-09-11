"""Prompt-editor service contract: append-only saves, validated context, no writes on read"""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.core.exceptions.exception_handler import _response_error_detail
from app.services.prompt_editor import PromptEditorService

WORKFLOW_ID = uuid4()
NODE_ID = "n1"
FIELD = "systemPrompt"
AGENT_NODE = {"id": NODE_ID, "type": "agentNode", "data": {"name": "A"}}


def _access_row(nodes=None):
    return SimpleNamespace(
        id=WORKFLOW_ID,
        agent_id=None,
        created_by=None,
        updated_at=datetime.now(timezone.utc),
        nodes=[AGENT_NODE] if nodes is None else nodes,
        agent_visible=True,
    )


def _version(version_number=1, *, node_id=NODE_ID, prompt_field=FIELD, content="text", label=None):
    return SimpleNamespace(
        id=uuid4(),
        workflow_id=WORKFLOW_ID,
        node_id=node_id,
        prompt_field=prompt_field,
        version_number=version_number,
        content=content,
        label=label,
        is_active=True,
        created_at=datetime.now(timezone.utc),
        created_by=None,
    )


def _service(nodes=None, workflow_found=True):
    db = AsyncMock()
    db.begin_nested = MagicMock()
    workflow_repo = AsyncMock()
    workflow_repo.get_access_row.return_value = _access_row(nodes) if workflow_found else None
    service = PromptEditorService(
        version_repo=AsyncMock(),
        config_repo=AsyncMock(),
        suite_repo=AsyncMock(),
        case_repo=AsyncMock(),
        workflow_repo=workflow_repo,
        db=db,
    )
    def _persist(orm):
        orm.id = uuid4()
        orm.created_at = datetime.now(timezone.utc)
        return orm

    service.version_repo.create.side_effect = _persist
    return service


def _integrity_error(sqlstate="23505"):
    return IntegrityError("INSERT ...", {}, SimpleNamespace(sqlstate=sqlstate))


async def _create(service, label=None, content="text"):
    from app.schemas.prompt_editor import PromptVersionCreate

    return await service.create_version(
        WORKFLOW_ID, NODE_ID, FIELD, PromptVersionCreate(content=content, label=label)
    )


class TestCreateVersionAppends:
    @pytest.mark.asyncio
    async def test_a_repeated_label_adds_a_row_instead_of_overwriting(self):
        service = _service()
        service.version_repo.next_version_number.side_effect = [1, 2]

        first = await _create(service, label="Optimized prompt", content="v1")
        second = await _create(service, label="Optimized prompt", content="v2")

        assert (first.version_number, second.version_number) == (1, 2)
        assert service.version_repo.create.await_count == 2
        service.version_repo.update.assert_not_awaited()
        assert first.content == "v1"
        assert first.created_at is not None

    @pytest.mark.asyncio
    async def test_the_save_runs_inside_one_savepoint(self):
        service = _service()
        service.version_repo.next_version_number.return_value = 1

        await _create(service)

        service.db.begin_nested.assert_called_once()
        service.version_repo.deactivate_all_for_context.assert_awaited_once_with(
            WORKFLOW_ID, NODE_ID, FIELD
        )


class TestCreateVersionConflicts:
    @pytest.mark.asyncio
    async def test_a_duplicate_number_becomes_a_readable_409(self):
        service = _service()
        service.version_repo.next_version_number.return_value = 1
        service.version_repo.create.side_effect = _integrity_error()

        with pytest.raises(AppException) as exc_info:
            await _create(service)

        assert exc_info.value.status_code == 409
        assert exc_info.value.error_key is ErrorKey.PROMPT_VERSION_CONFLICT
        assert exc_info.value.error_detail == "Another save completed first. Try again."

    @pytest.mark.asyncio
    async def test_other_integrity_failures_keep_their_generic_handling(self):
        service = _service()
        service.version_repo.next_version_number.return_value = 1
        service.version_repo.create.side_effect = _integrity_error(sqlstate="23503")

        with pytest.raises(IntegrityError):
            await _create(service)

    def test_the_conflict_detail_reaches_the_user_outside_dev(self, monkeypatch):
        monkeypatch.delenv("ENV", raising=False)
        error = AppException(
            status_code=409,
            error_key=ErrorKey.PROMPT_VERSION_CONFLICT,
            error_detail="Another save completed first. Try again.",
        )

        assert _response_error_detail(error) == "Another save completed first. Try again."


class TestContextValidation:
    @pytest.mark.asyncio
    async def test_a_node_outside_the_saved_workflow_cannot_be_written_to(self):
        service = _service(nodes=[])

        with pytest.raises(AppException) as exc_info:
            await _create(service)

        assert exc_info.value.status_code == 400
        assert exc_info.value.error_key is ErrorKey.PROMPT_CONTEXT_INVALID
        assert "save the workflow" in exc_info.value.error_detail

    @pytest.mark.asyncio
    async def test_the_legacy_shared_id_gets_its_own_explanation(self):
        from app.schemas.prompt_editor import PromptVersionCreate

        service = _service(nodes=[])

        with pytest.raises(AppException) as exc_info:
            await service.create_version(
                WORKFLOW_ID, "agent-config", FIELD, PromptVersionCreate(content="x")
            )

        assert exc_info.value.error_key is ErrorKey.PROMPT_CONTEXT_INVALID
        assert "read-only" in exc_info.value.error_detail

    @pytest.mark.asyncio
    async def test_an_unregistered_field_on_a_live_node_is_rejected(self):
        from app.schemas.prompt_editor import PromptVersionCreate

        service = _service()

        with pytest.raises(AppException) as exc_info:
            await service.create_version(
                WORKFLOW_ID, NODE_ID, "smartPrompt", PromptVersionCreate(content="x")
            )

        assert exc_info.value.status_code == 400
        assert exc_info.value.error_key is ErrorKey.PROMPT_FIELD_NOT_SUPPORTED

    @pytest.mark.asyncio
    async def test_a_workflow_with_no_stored_graph_reads_as_a_missing_node(self):
        """MLModelDetail creates node-less workflows, so the column can be NULL."""
        service = _service(nodes=[])
        service.workflow_repo.get_access_row.return_value.nodes = None
        service.version_repo.get_versions_for_context.return_value = []
        service.config_repo.get_by_context.return_value = None

        history = await service.get_history(WORKFLOW_ID, NODE_ID, FIELD)

        assert history.node_missing is True
        assert history.node_type is None

    @pytest.mark.asyncio
    async def test_an_unknown_workflow_is_a_404(self):
        service = _service(workflow_found=False)

        with pytest.raises(AppException) as exc_info:
            await _create(service)

        assert exc_info.value.status_code == 404
        assert exc_info.value.error_key is ErrorKey.WORKFLOW_NOT_FOUND


class TestGetConfig:
    @pytest.mark.asyncio
    async def test_a_context_with_no_row_reads_back_empty_and_writes_nothing(self):
        service = _service()
        service.config_repo.get_by_context.return_value = None

        config = await service.get_config(WORKFLOW_ID, NODE_ID, FIELD)

        assert config.id is None
        assert config.created_at is None
        assert config.gold_suite_id is None
        service.config_repo.create.assert_not_awaited()
        service.config_repo.get_or_create.assert_not_awaited()


class TestGetHistory:
    @pytest.mark.asyncio
    async def test_it_carries_the_field_label_and_inline_check_support(self):
        service = _service()
        service.version_repo.get_versions_for_context.side_effect = [[_version(1)], []]
        service.config_repo.get_by_context.side_effect = [
            SimpleNamespace(gold_suite_id=None),
            None,
        ]

        history = await service.get_history(WORKFLOW_ID, NODE_ID, FIELD)

        assert history.node_type == "agentNode"
        assert history.node_missing is False
        assert history.field_label == "System Prompt"
        assert history.inline_check_supported is True
        assert history.unsupported_reason is None
        assert history.legacy_shared is None
        assert [v.version_number for v in history.versions] == [1]

    @pytest.mark.asyncio
    async def test_a_field_without_the_inline_check_explains_itself(self):
        service = _service()
        service.version_repo.get_versions_for_context.side_effect = [[], []]
        service.config_repo.get_by_context.side_effect = [None, None]

        history = await service.get_history(WORKFLOW_ID, NODE_ID, "userPrompt")

        assert history.field_label == "User Prompt"
        assert history.inline_check_supported is False
        assert history.unsupported_reason

    @pytest.mark.asyncio
    async def test_the_legacy_bucket_is_surfaced_when_it_holds_something(self):
        service = _service()
        service.version_repo.get_versions_for_context.side_effect = [
            [],
            [_version(1, node_id="agent-config")],
        ]
        service.config_repo.get_by_context.side_effect = [None, None]

        history = await service.get_history(WORKFLOW_ID, NODE_ID, FIELD)

        assert history.legacy_shared is not None
        assert history.legacy_shared.node_id == "agent-config"
        assert len(history.legacy_shared.versions) == 1

    @pytest.mark.asyncio
    async def test_a_node_type_with_no_bucket_never_queries_one(self):
        service = _service(nodes=[{"id": NODE_ID, "type": "routerNode"}])
        service.version_repo.get_versions_for_context.return_value = []
        service.config_repo.get_by_context.return_value = None

        history = await service.get_history(WORKFLOW_ID, NODE_ID, FIELD)

        assert history.legacy_shared is None
        assert service.version_repo.get_versions_for_context.await_count == 1

    @pytest.mark.asyncio
    async def test_a_removed_node_still_reads_but_reports_itself_missing(self):
        service = _service(nodes=[])
        service.version_repo.get_versions_for_context.return_value = [_version(1)]
        service.config_repo.get_by_context.return_value = None

        history = await service.get_history(WORKFLOW_ID, NODE_ID, FIELD)

        assert history.node_missing is True
        assert history.field_label is None
        assert history.inline_check_supported is False
        assert history.legacy_shared is None
        assert len(history.versions) == 1

    @pytest.mark.asyncio
    async def test_the_node_type_hint_restores_a_removed_node_s_context(self):
        service = _service(nodes=[])
        service.version_repo.get_versions_for_context.side_effect = [
            [_version(1)],
            [_version(1, node_id="agent-config")],
        ]
        service.config_repo.get_by_context.side_effect = [None, None]

        history = await service.get_history(WORKFLOW_ID, NODE_ID, FIELD, "agentNode")

        assert history.node_missing is True
        assert history.node_type == "agentNode"
        assert history.field_label == "System Prompt"
        assert history.legacy_shared is not None
        assert history.legacy_shared.node_id == "agent-config"

    @pytest.mark.asyncio
    async def test_a_hint_naming_no_supported_field_is_ignored(self):
        service = _service(nodes=[])
        service.version_repo.get_versions_for_context.return_value = []
        service.config_repo.get_by_context.return_value = None

        history = await service.get_history(WORKFLOW_ID, NODE_ID, FIELD, "madeUpNode")

        assert history.node_type is None
        assert history.legacy_shared is None
        assert service.version_repo.get_versions_for_context.await_count == 1

    @pytest.mark.asyncio
    async def test_reading_a_legacy_bucket_does_not_repeat_it_as_its_own_legacy(self):
        service = _service(nodes=[])
        service.version_repo.get_versions_for_context.return_value = [
            _version(1, node_id="agent-config")
        ]
        service.config_repo.get_by_context.return_value = None

        history = await service.get_history(
            WORKFLOW_ID, "agent-config", FIELD, "agentNode"
        )

        assert history.legacy_shared is None
        assert len(history.versions) == 1
        assert service.version_repo.get_versions_for_context.await_count == 1
        assert service.config_repo.get_by_context.await_count == 1

    @pytest.mark.asyncio
    async def test_the_stored_type_wins_over_a_conflicting_hint(self):
        service = _service(nodes=[{"id": NODE_ID, "type": "routerNode"}])
        service.version_repo.get_versions_for_context.return_value = []
        service.config_repo.get_by_context.return_value = None

        history = await service.get_history(WORKFLOW_ID, NODE_ID, FIELD, "agentNode")

        assert history.node_type == "routerNode"
        assert history.legacy_shared is None


class TestDeleteVersion:
    @pytest.mark.asyncio
    async def test_an_unknown_version_is_a_404(self):
        service = _service()
        service.version_repo.get_by_id.return_value = None

        with pytest.raises(AppException) as exc_info:
            await service.delete_version(uuid4())

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_deletion_is_scoped_to_the_version_not_the_workflow(self):
        service = _service()
        version = _version(1)
        service.version_repo.get_by_id.return_value = version

        await service.delete_version(version.id)

        service.version_repo.soft_delete.assert_awaited_once_with(version)
        service.workflow_repo.get_access_row.assert_not_awaited()


class TestLinkGoldSuite:
    @pytest.mark.asyncio
    async def test_it_needs_a_live_node(self):
        service = _service(nodes=[])

        with pytest.raises(AppException) as exc_info:
            await service.link_gold_suite(WORKFLOW_ID, NODE_ID, FIELD)

        assert exc_info.value.error_key is ErrorKey.PROMPT_CONTEXT_INVALID

    @pytest.mark.asyncio
    async def test_it_creates_the_config_row_and_leaves_the_commit_to_the_boundary(self):
        service = _service()
        config = SimpleNamespace(
            id=uuid4(),
            workflow_id=WORKFLOW_ID,
            node_id=NODE_ID,
            prompt_field=FIELD,
            gold_suite_id=None,
            created_at=datetime.now(timezone.utc),
        )
        service.config_repo.get_or_create.return_value = config
        suite_id = uuid4()
        service.suite_repo.create.side_effect = lambda orm: SimpleNamespace(id=suite_id)

        result = await service.link_gold_suite(WORKFLOW_ID, NODE_ID, FIELD)

        service.config_repo.get_or_create.assert_awaited_once_with(WORKFLOW_ID, NODE_ID, FIELD)
        assert result.gold_suite_id == suite_id
        service.db.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_an_unknown_suite_id_is_a_404(self):
        service = _service()
        service.config_repo.get_or_create.return_value = SimpleNamespace(gold_suite_id=None)
        service.suite_repo.get_by_id.return_value = None

        with pytest.raises(AppException) as exc_info:
            await service.link_gold_suite(WORKFLOW_ID, NODE_ID, FIELD, suite_id=uuid4())

        assert exc_info.value.status_code == 404
