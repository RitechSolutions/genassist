from uuid import UUID

from injector import inject

from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.core.utils.enums.issue_status_enum import DEFAULT_ISSUE_STATUS_KEY
from app.db.models.issue_status import IssueStatusModel
from app.repositories.issue_status import IssueStatusRepository
from app.schemas.issue_status import IssueStatusCreate, IssueStatusEdit, IssueStatusOrder, IssueStatusRead


@inject
class IssueStatusService:
    def __init__(self, repo: IssueStatusRepository):
        self.repo = repo

    async def list_statuses(self) -> list[IssueStatusRead]:
        return [IssueStatusRead.model_validate(status) for status in await self.repo.list_ordered()]

    async def create(self, dto: IssueStatusCreate) -> IssueStatusRead:
        if await self.repo.get_by_key(dto.key):
            raise AppException(ErrorKey.ISSUE_STATUS_KEY_TAKEN, status_code=409)
        status = IssueStatusModel(**dto.model_dump(mode="json"), position=await self.repo.max_position() + 1)
        return IssueStatusRead.model_validate(await self.repo.create(status))

    async def update(self, status_id: UUID, dto: IssueStatusEdit) -> IssueStatusRead:
        status = await self.repo.get_by_id(status_id)
        if status is None:
            raise AppException(ErrorKey.ISSUE_STATUS_NOT_FOUND, status_code=404)
        changes = dto.model_dump(mode="json", exclude_none=True)
        if status.key == DEFAULT_ISSUE_STATUS_KEY and (
            changes.get("is_active") == 0 or changes.get("category", status.category) != status.category
        ):
            raise AppException(ErrorKey.ISSUE_STATUS_PROTECTED, status_code=422)
        for field, value in changes.items():
            setattr(status, field, value)
        return IssueStatusRead.model_validate(await self.repo.update(status))

    async def reorder(self, dto: IssueStatusOrder) -> list[IssueStatusRead]:
        active_keys = {status.key for status in await self.repo.list_ordered() if status.is_active}
        if len(dto.keys) != len(active_keys) or set(dto.keys) != active_keys:
            raise AppException(ErrorKey.ISSUE_STATUS_ORDER_INVALID, status_code=422)
        await self.repo.set_positions(dto.keys)
        return await self.list_statuses()
