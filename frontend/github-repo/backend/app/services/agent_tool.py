from typing import List
from uuid import UUID
from injector import inject
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.db.models import ToolModel
from app.repositories.tool import ToolRepository
from app.schemas.agent_tool import ToolConfigBase, ToolConfigRead

@inject
class ToolService:
    """
    Business-logic layer.
    – Exposes / consumes Pydantic models.
    – Uses ToolRepository (ORM) under the hood.
    """

    def __init__(self, repository: ToolRepository):
        self.repository = repository

    # ---------- READ ----------
    async def get_all(self) -> List[ToolConfigRead]:
        orm_objs = await self.repository.get_all()
        return [ToolConfigRead.model_validate(o, from_attributes=True) for o in orm_objs]

    async def get_by_id(self, tool_id: UUID) -> ToolConfigRead:
        orm_obj = await self.repository.get_by_id(tool_id)
        if not orm_obj:
            raise AppException(error_key=ErrorKey.TOOL_NOT_FOUND, status_code=404)
        return ToolConfigRead.model_validate(orm_obj, from_attributes=True)

    async def get_by_ids(self, ids: List[UUID]) -> List[ToolConfigRead]:
        orm_objs = await self.repository.get_by_ids(ids)
        return [ToolConfigRead.model_validate(o, from_attributes=True) for o in orm_objs]

    # ---------- WRITE ----------
    async def create(self, data: ToolConfigBase) -> ToolConfigRead:
        # convert schema ➜ ORM
        new_tool = ToolModel(**data.model_dump())
        created = await self.repository.create(new_tool)
        return ToolConfigRead.model_validate(created, from_attributes=True)

    async def update(self, tool_id: UUID, data: ToolConfigBase) -> ToolConfigRead:
        orm_obj = await self.repository.get_by_id(tool_id)
        if not orm_obj:
            raise AppException(status_code=404, error_key=ErrorKey.TOOL_NOT_FOUND)

        # mutate ORM object in place
        for field, value in data.model_dump().items():
            setattr(orm_obj, field, value)

        updated = await self.repository.update(orm_obj)
        return ToolConfigRead.model_validate(updated, from_attributes=True)

    async def delete(self, tool_id: UUID) -> None:
        orm_obj = await self.repository.get_by_id(tool_id)
        if not orm_obj:
            raise AppException(status_code=404, error_key=ErrorKey.TOOL_NOT_FOUND)
        await self.repository.delete(orm_obj)
