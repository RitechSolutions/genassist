import logging
from typing import List, Optional
from uuid import UUID

from injector import inject
from sqlalchemy import select

from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.core.utils.workflow_secrets import (
    decrypt_hidden_defaults,
    encrypt_hidden_defaults,
)
from app.db.events.group_scope import GROUP_SCOPE_BYPASS_FLAG
from app.db.models.agent import AgentModel
from app.db.models.operator import OperatorModel
from app.db.models.user import UserModel
from app.db.models.workflow import WorkflowModel
from app.repositories.workflow import WorkflowRepository
from app.schemas.workflow import (
    WorkflowCreate,
    WorkflowInDB,
    WorkflowMinimal,
    WorkflowSummary,
    WorkflowUpdate,
)

logger = logging.getLogger(__name__)

@inject
class WorkflowService:
    """
    Business-logic layer.
    – Exposes / consumes Pydantic models.
    – Uses WorkflowRepository (ORM) under the hood.
    """

    def __init__(self, repository: WorkflowRepository):
        self.repository = repository

    # ---------- READ ----------
    async def get_all_minimal(self) -> List[WorkflowMinimal]:
        rows = await self.repository.get_all_minimal()
        return [WorkflowMinimal.model_validate(r, from_attributes=True) for r in rows]

    async def get_visible_minimal(self) -> List[WorkflowMinimal]:
        """What the caller may pick from, matching Agent Studio."""
        rows = await self.repository.get_visible_minimal()
        return [WorkflowMinimal.model_validate(r, from_attributes=True) for r in rows]

    async def get_minimal_by_ids(self, ids: List[UUID]) -> List[WorkflowMinimal]:
        rows = await self.repository.get_minimal_by_ids(ids)
        return [WorkflowMinimal.model_validate(r, from_attributes=True) for r in rows]

    async def get_summaries_by_agent(self, agent_id: UUID) -> List[WorkflowSummary]:
        rows = await self.repository.get_summaries_by_agent(agent_id)
        username_map = await self._resolve_usernames(rows)
        result: List[WorkflowSummary] = []
        for r in rows:
            summary = WorkflowSummary.model_validate(r, from_attributes=True)
            editor_id = r.updated_by or r.created_by
            summary.updated_by_username = username_map.get(editor_id)
            result.append(summary)
        return result

    async def get_all(self) -> List[WorkflowInDB]:
        orm_objs = await self.repository.get_all()
        username_map = await self._resolve_usernames(orm_objs)
        result: List[WorkflowInDB] = []
        for o in orm_objs:
            wf = WorkflowInDB.model_validate(o, from_attributes=True)
            wf.nodes = decrypt_hidden_defaults(wf.nodes)
            # "who modified last": prefer updated_by, fall back to the creator
            # for workflows that have never been edited since creation.
            editor_id = o.updated_by or o.created_by
            wf.updated_by_username = username_map.get(editor_id)
            result.append(wf)
        return result

    async def _resolve_usernames(self, orm_objs) -> dict:
        """Batch-resolve audit user UUIDs to usernames for display.

        Users may be group-scoped; bypass the scope filter so a display-name
        lookup can never be silently filtered out.
        """
        user_ids = {
            uid
            for o in orm_objs
            for uid in (o.updated_by, o.created_by)
            if uid is not None
        }
        if not user_ids:
            return {}
        rows = await self.repository.db.execute(
            select(UserModel.id, UserModel.username)
            .where(UserModel.id.in_(user_ids))
            .execution_options(**{GROUP_SCOPE_BYPASS_FLAG: True})
        )
        return {row.id: row.username for row in rows}

    async def get_active_version_id(self, workflow_id: UUID) -> Optional[UUID]:
        """The live version of the workflow's agent — what the builder marks Active.

        ``None`` when the workflow has no agent or the agent points nowhere, so
        callers can fall back to the version they already hold.

        Agents are group-scoped but workflows are not; the scope filter is
        bypassed so this pointer resolves to the same version for every caller
        instead of silently falling back for some. Only the id is read.
        """
        workflow = await self.repository.get_by_id(workflow_id)
        if not workflow or not workflow.agent_id:
            return None
        rows = await self.repository.db.execute(
            select(AgentModel.workflow_id)
            .where(AgentModel.id == workflow.agent_id)
            .execution_options(**{GROUP_SCOPE_BYPASS_FLAG: True})
        )
        return rows.scalar_one_or_none()

    async def get_by_id(self, workflow_id: UUID) -> WorkflowInDB:
        orm_obj = await self.repository.get_by_id(workflow_id)
        if not orm_obj:
            raise AppException(error_key=ErrorKey.WORKFLOW_NOT_FOUND, status_code=404)
        wf = WorkflowInDB.model_validate(orm_obj, from_attributes=True)
        wf.nodes = decrypt_hidden_defaults(wf.nodes)
        return wf

    async def get_by_ids(self, ids: List[UUID]) -> List[WorkflowInDB]:
        orm_objs = await self.repository.get_by_ids(ids)
        result: List[WorkflowInDB] = []
        for o in orm_objs:
            wf = WorkflowInDB.model_validate(o, from_attributes=True)
            wf.nodes = decrypt_hidden_defaults(wf.nodes)
            result.append(wf)
        return result

    @staticmethod
    def _validate_sub_agents(payload: dict) -> None:
        """Save-time sub-agent check"""
        from pydantic import ValidationError

        from app.core.exceptions.error_messages import ErrorKey
        from app.modules.workflow.agents.sub_agents.graph import (
            SubAgentTopologyError,
            validate_sub_agent_topology,
        )
        from app.modules.workflow.agents.sub_agents.models import SubAgentConfig

        try:
            validate_sub_agent_topology(payload.get("nodes"), payload.get("edges"))
        except SubAgentTopologyError as e:
            raise AppException(
                error_key=ErrorKey.SUB_AGENT_INVALID_TOPOLOGY,
                status_code=400,
                error_variables=[str(e)],
                error_detail=str(e),
            ) from e

        for node in payload.get("nodes") or []:
            if node.get("type") != "subAgentNode":
                continue
            try:
                SubAgentConfig.model_validate(node.get("data") or {})
            except ValidationError as e:
                name = (node.get("data") or {}).get("name") or node.get("id")
                detail = f"'{name}': {e.errors()[0].get('msg', 'invalid configuration')}"
                raise AppException(
                    error_key=ErrorKey.SUB_AGENT_INVALID_CONFIG,
                    status_code=400,
                    error_variables=[detail],
                    error_detail=detail,
                ) from e

    # ---------- WRITE ----------
    async def create(self, data: WorkflowCreate) -> WorkflowInDB:
        # convert schema ➜ ORM
        payload = data.model_dump()
        self._validate_sub_agents(payload)
        # Encrypt hidden Chat Input defaults so they are never stored in plaintext.
        payload["nodes"] = encrypt_hidden_defaults(payload.get("nodes"))
        new_workflow = WorkflowModel(**payload)
        created = await self.repository.create(new_workflow)
        result = WorkflowInDB.model_validate(created, from_attributes=True)
        result.nodes = decrypt_hidden_defaults(result.nodes)
        return result

    async def update(self, workflow_id: UUID, data: WorkflowUpdate) -> WorkflowInDB:
        orm_obj = await self.repository.get_by_id(workflow_id, eager=["agent"])
        if not orm_obj:
            raise AppException(status_code=404, error_key=ErrorKey.WORKFLOW_NOT_FOUND)

        # mutate ORM object in place
        payload = data.model_dump()
        self._validate_sub_agents(payload)
        # Encrypt hidden Chat Input defaults so they are never stored in plaintext.
        payload["nodes"] = encrypt_hidden_defaults(payload.get("nodes"))
        for field, value in payload.items():
            setattr(orm_obj, field, value)

        updated = await self.repository.update(orm_obj)
        if updated.agent:
            await self._invalidate_agent_caches(updated.agent.id)
        result = WorkflowInDB.model_validate(updated, from_attributes=True)
        result.nodes = decrypt_hidden_defaults(result.nodes)
        return result

    async def delete(self, workflow_id: UUID) -> None:
        orm_obj = await self.repository.get_by_id(workflow_id, eager=["agent"])
        if not orm_obj:
            raise AppException(status_code=404, error_key=ErrorKey.WORKFLOW_NOT_FOUND)
        if orm_obj.agent:
            await self._invalidate_agent_caches(orm_obj.agent.id)
        await self.repository.delete(orm_obj)

    async def soft_delete_by_agent(self, agent_id: UUID, commit: bool = True) -> None:
        """Retire every version of an agent's workflow when the agent is deleted."""
        await self.repository.soft_delete_by_agent(agent_id, commit=commit)

    async def _invalidate_agent_caches(self, agent_id: UUID) -> None:
        """Best-effort bust of every agent cache that embeds the workflow.

        Editing a workflow changes data cached under both the agent-id keyed
        (`agents:get_by_id_full`) and the owner-user-id keyed
        (`agents:get_by_user_id`) namespaces. The latter is what the conversation
        bootstrap (`get_agent_for_start` → `get_by_user_id`) reads, so without
        busting it a node change (e.g. removing the Voice Agent node) stays
        invisible to the widget until the 5-minute TTL lapses.

        This runs after the workflow has already been persisted, so it must never
        raise: a failure here only means the stale entry lingers until its TTL,
        which is strictly better than failing an otherwise-successful save.
        """
        # invalidate_cache stays lazily imported to avoid an import cycle (mirrors
        # the original update/delete callers).
        from app.cache.redis_cache import invalidate_cache

        try:
            await invalidate_cache("agents:get_by_id_full", agent_id)

            # AgentModel is group-scoped; bypass the scope filter (mirroring
            # AgentRepository) so the owner lookup can't be silently filtered out.
            owner_user_id = (
                await self.repository.db.execute(
                    select(OperatorModel.user_id)
                    .join(AgentModel, AgentModel.operator_id == OperatorModel.id)
                    .where(AgentModel.id == agent_id)
                    .execution_options(**{GROUP_SCOPE_BYPASS_FLAG: True})
                )
            ).scalar_one_or_none()
            if owner_user_id is not None:
                await invalidate_cache("agents:get_by_user_id", owner_user_id)
        except Exception:
            logger.exception(
                "Failed to invalidate agent caches for agent_id=%s after workflow "
                "change; stale entries will expire on their TTL.",
                agent_id,
            )