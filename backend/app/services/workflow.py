import logging
from typing import List
from uuid import UUID
from fastapi import Depends
from injector import inject
from sqlalchemy import select
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.db.events.group_scope import GROUP_SCOPE_BYPASS_FLAG
from app.db.models.agent import AgentModel
from app.db.models.operator import OperatorModel
from app.db.models.user import UserModel
from app.db.models.workflow import WorkflowModel
from app.repositories.workflow import WorkflowRepository
from app.schemas.workflow import WorkflowCreate, WorkflowInDB, WorkflowMinimal, WorkflowUpdate
from app.core.utils.workflow_secrets import (
    decrypt_hidden_defaults,
    encrypt_hidden_defaults,
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

    # ---------- WRITE ----------
    async def create(self, data: WorkflowCreate) -> WorkflowInDB:
        # convert schema ➜ ORM
        payload = data.model_dump()
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
