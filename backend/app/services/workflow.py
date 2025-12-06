from typing import List
from uuid import UUID
from fastapi import Depends
from injector import inject

from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.db.models.workflow import WorkflowModel
from app.repositories.workflow import WorkflowRepository
from app.schemas.workflow import WorkflowCreate, WorkflowInDB, WorkflowUpdate


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
    async def get_all(self) -> List[WorkflowInDB]:
        orm_objs = await self.repository.get_all()
        return [WorkflowInDB.model_validate(o, from_attributes=True) for o in orm_objs]

    async def get_by_id(self, workflow_id: UUID) -> WorkflowInDB:
        orm_obj = await self.repository.get_by_id(workflow_id)
        if not orm_obj:
            raise AppException(error_key=ErrorKey.WORKFLOW_NOT_FOUND, status_code=404)
        return WorkflowInDB.model_validate(orm_obj, from_attributes=True)

    async def get_by_ids(self, ids: List[UUID]) -> List[WorkflowInDB]:
        orm_objs = await self.repository.get_by_ids(ids)
        return [WorkflowInDB.model_validate(o, from_attributes=True) for o in orm_objs]

    # ---------- WRITE ----------
    async def create(self, data: WorkflowCreate) -> WorkflowInDB:
        # convert schema ➜ ORM
        new_workflow = WorkflowModel(**data.model_dump())
        created = await self.repository.create(new_workflow)
        return WorkflowInDB.model_validate(created, from_attributes=True)

    async def update(self, workflow_id: UUID, data: WorkflowUpdate) -> WorkflowInDB:
        orm_obj = await self.repository.get_by_id(workflow_id)
        if not orm_obj:
            raise AppException(status_code=404, error_key=ErrorKey.WORKFLOW_NOT_FOUND)

        # mutate ORM object in place
        for field, value in data.model_dump().items():
            setattr(orm_obj, field, value)

        updated = await self.repository.update(orm_obj)
        return WorkflowInDB.model_validate(updated, from_attributes=True)

    async def delete(self, tool_id: UUID) -> None:
        orm_obj = await self.repository.get_by_id(tool_id)
        if not orm_obj:
            raise AppException(status_code=404, error_key=ErrorKey.WORKFLOW_NOT_FOUND)
        await self.repository.delete(orm_obj)
