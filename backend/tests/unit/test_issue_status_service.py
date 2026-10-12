"""Unit tests for managing the configurable issue statuses, with a fake repository"""

from types import SimpleNamespace
from uuid import uuid4

import pytest

import app.db.models  # noqa: F401 — registers mappers for ORM construction
import app.db.models.test_suite  # noqa: F401
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.schemas.issue_status import IssueStatusCreate, IssueStatusEdit, IssueStatusOrder
from app.services.issue_status import IssueStatusService


def _status(key, category="in_progress", position=0, is_active=1):
    return SimpleNamespace(
        id=uuid4(), key=key, label=key.title(), category=category, position=position, color="blue", is_active=is_active
    )


class FakeRepo:
    def __init__(self, statuses):
        self.statuses = statuses
        self.positions = None

    async def list_ordered(self):
        return self.statuses

    async def get_by_key(self, key):
        return next((status for status in self.statuses if status.key == key), None)

    async def get_by_id(self, status_id):
        return next((status for status in self.statuses if status.id == status_id), None)

    async def max_position(self):
        return max(status.position for status in self.statuses)

    async def create(self, status):
        status.id, status.is_active = uuid4(), 1
        return status

    async def update(self, status):
        return status

    async def set_positions(self, keys):
        self.positions = keys


def _service():
    statuses = [
        _status("open", "todo", 0),
        _status("in_progress", position=1),
        _status("resolved", "done", 2),
        _status("escalated", position=3, is_active=0),
    ]
    return IssueStatusService(FakeRepo(statuses)), statuses


@pytest.mark.asyncio
async def test_create_appends_after_the_last_position():
    service, _ = _service()
    created = await service.create(
        IssueStatusCreate(key="qa_approved", label="QA Approved", category="in_progress", color="teal")
    )
    assert created.position == 4


@pytest.mark.asyncio
async def test_create_refuses_a_taken_key():
    service, _ = _service()
    with pytest.raises(AppException) as error:
        await service.create(IssueStatusCreate(key="escalated", label="Again", category="todo", color="red"))
    assert (error.value.error_key, error.value.status_code) == (ErrorKey.ISSUE_STATUS_KEY_TAKEN, 409)


@pytest.mark.asyncio
@pytest.mark.parametrize("edit", [IssueStatusEdit(is_active=0), IssueStatusEdit(label="New", category="done")])
async def test_open_cannot_be_retired_or_leave_todo(edit):
    service, statuses = _service()
    with pytest.raises(AppException) as error:
        await service.update(statuses[0].id, edit)
    assert (error.value.error_key, error.value.status_code) == (ErrorKey.ISSUE_STATUS_PROTECTED, 422)
    assert (statuses[0].label, statuses[0].category) == ("Open", "todo")


@pytest.mark.asyncio
async def test_open_keeps_label_and_colour_edits():
    service, statuses = _service()
    updated = await service.update(statuses[0].id, IssueStatusEdit(label="New", category="todo", color="red"))
    assert (updated.key, updated.label, updated.category, updated.color) == ("open", "New", "todo", "red")


@pytest.mark.asyncio
async def test_update_of_an_unknown_status_is_not_found():
    service, _ = _service()
    with pytest.raises(AppException) as error:
        await service.update(uuid4(), IssueStatusEdit(label="x"))
    assert error.value.status_code == 404


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "keys", [["open", "in_progress"], ["open", "in_progress", "resolved", "escalated"], ["open", "open", "resolved"]]
)
async def test_reorder_needs_every_active_key_exactly_once(keys):
    service, _ = _service()
    with pytest.raises(AppException) as error:
        await service.reorder(IssueStatusOrder(keys=keys))
    assert (error.value.error_key, error.value.status_code) == (ErrorKey.ISSUE_STATUS_ORDER_INVALID, 422)


@pytest.mark.asyncio
async def test_reorder_writes_the_given_order():
    service, _ = _service()
    await service.reorder(IssueStatusOrder(keys=["resolved", "open", "in_progress"]))
    assert service.repo.positions == ["resolved", "open", "in_progress"]
