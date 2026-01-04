# app/services/knowledge_base_service.py
from typing import List, Optional
from uuid import UUID
from fastapi import logger
from injector import inject
from neo4j import AsyncSession
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.db.models.knowledge_base import KnowledgeBaseModel
from app.repositories.knowledge_base import KnowledgeBaseRepository
from app.schemas.agent_knowledge import KBCreate, KBRead

import logging
logger = logging.getLogger(__name__)

@inject
class KnowledgeBaseService:
    """
    – Accepts / returns Pydantic models.
    – Converts to / from the ORM entity.
    """

    def __init__(self, repository: KnowledgeBaseRepository):
        self.repository = repository

    # ─────────────── READ ───────────────
    async def get_all(self) -> List[KBRead]:
        objs = await self.repository.get_all()
        return [KBRead.model_validate(o, from_attributes=True) for o in objs]

    async def get_by_id(self, kb_id: UUID) -> KBRead:
        obj = await self.repository.get_by_id(kb_id)
        if not obj:
            raise AppException(status_code=404, error_key=ErrorKey.KB_NOT_FOUND)
        return KBRead.model_validate(obj, from_attributes=True)

    async def get_by_ids(self, ids: List[UUID]) -> List[KBRead]:
        objs = await self.repository.get_by_ids(ids)
        return [KBRead.model_validate(o, from_attributes=True) for o in objs]

    # ─────────────── WRITE ───────────────
    async def create(self, data: KBCreate) -> KBRead:
        orm_obj = KnowledgeBaseModel(**data.model_dump())
        created = await self.repository.create(orm_obj)
        return KBRead.model_validate(created, from_attributes=True)

    async def update(self, kb_id: UUID, data: KBCreate) -> KBRead:
        orm_obj = await self.repository.get_by_id(kb_id)
        if not orm_obj:
            raise AppException(status_code=404, error_key=ErrorKey.KB_NOT_FOUND)

        for field, value in data.model_dump().items():
            setattr(orm_obj, field, value)

        updated = await self.repository.update(orm_obj)
        return KBRead.model_validate(updated, from_attributes=True)

    async def delete(self, kb_id: UUID) -> None:
        orm_obj = await self.repository.get_by_id(kb_id)
        if not orm_obj:
            raise AppException(status_code=404, error_key=ErrorKey.KB_NOT_FOUND)
        await self.repository.delete(orm_obj)
