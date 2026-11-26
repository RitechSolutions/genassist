"""Deleting a template withdraws its shared copies; only the author sees why it was rejected."""
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.core.exceptions.exception_classes import AppException
from app.core.tenant_scope import TenantContextError
from app.core.utils.enums.template_status_enum import TemplateStatus
from app.repositories.template import TemplateRepository
from app.schemas.template import TemplateRead
from app.services.template import TemplateService

TENANT = "acme"


@pytest.fixture(autouse=True)
def tenant(monkeypatch):
    monkeypatch.setattr("app.services.template.require_tenant_context", lambda: TENANT)
    monkeypatch.setattr("app.services.template.get_tenant_context", lambda: TENANT)


def _service(master, private_row=None):
    repository = AsyncMock()
    repository.get_by_id.return_value = private_row
    repository.get_locked.return_value = private_row
    service = TemplateService(repository=repository, workflow_service=AsyncMock(), agent_config_service=AsyncMock())

    @asynccontextmanager
    async def master_repo():
        yield master

    service._master_repo = master_repo
    return service


def _row(title, **fields):
    return SimpleNamespace(id=uuid4(), title=title, graph={"nodes": []}, **fields)


def _private(owner):
    return SimpleNamespace(id=uuid4(), is_deleted=0, created_by=owner, status=TemplateStatus.PRIVATE)


@pytest.mark.asyncio
async def test_delete_withdraws_every_shared_copy_before_the_template():
    user = uuid4()
    private = _private(user)
    master = AsyncMock()
    order = []
    master.soft_delete_published.side_effect = lambda *args: order.append("shared copies")
    service = _service(master, private)
    service.repository.soft_delete.side_effect = lambda row: order.append("template")

    await service.delete_template(private.id, user)

    assert order == ["shared copies", "template"]
    source, statuses, tenant = master.soft_delete_published.call_args.args
    assert (source, tenant) == (private.id, TENANT)
    assert set(statuses) == {TemplateStatus.PENDING, TemplateStatus.APPROVED, TemplateStatus.REJECTED}
    # The row stays locked until the request ends, so a publish at the same moment waits.
    service.repository.get_locked.assert_awaited_once_with(private.id)


@pytest.mark.asyncio
async def test_withdraw_takes_the_pending_or_approved_copy_only():
    user = uuid4()
    private = _private(user)
    master = AsyncMock()
    service = _service(master, private)

    await service.unpublish(private.id, user)

    source, statuses, tenant = master.soft_delete_published.call_args.args
    assert (source, set(statuses), tenant) == (private.id, {TemplateStatus.PENDING, TemplateStatus.APPROVED}, TENANT)
    service.repository.soft_delete.assert_not_awaited()
    # Locked like publish, so a withdraw can't slip in while a publish is still saving its copy.
    service.repository.get_locked.assert_awaited_once_with(private.id)


@pytest.mark.asyncio
async def test_withdrawing_fails_closed_without_a_tenant(monkeypatch):
    def no_tenant():
        raise TenantContextError("no tenant")

    monkeypatch.setattr("app.services.template.require_tenant_context", no_tenant)
    user = uuid4()
    private = _private(user)
    master = AsyncMock()
    service = _service(master, private)

    with pytest.raises(TenantContextError):
        await service.delete_template(private.id, user)

    master.soft_delete_published.assert_not_awaited()
    service.repository.soft_delete.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "callers, status",
    [
        (False, TemplateStatus.PRIVATE),
        # A shared copy in the master database, even one that carries the caller's user id.
        (True, TemplateStatus.APPROVED),
    ],
)
async def test_only_the_callers_private_template_can_be_deleted(callers, status):
    caller = uuid4()
    row = SimpleNamespace(id=uuid4(), is_deleted=0, created_by=caller if callers else uuid4(), status=status)
    master = AsyncMock()
    service = _service(master, row)

    with pytest.raises(AppException) as exc:
        await service.delete_template(row.id, caller)

    assert exc.value.status_code == 404
    master.soft_delete_published.assert_not_awaited()
    service.repository.soft_delete.assert_not_awaited()


@pytest.mark.asyncio
async def test_withdrawing_touches_only_this_tenants_copies():
    db = MagicMock()
    db.execute = AsyncMock()
    db.flush = AsyncMock()
    source = uuid4()

    await TemplateRepository(db).soft_delete_published(source, (TemplateStatus.APPROVED,), "acme")

    statement = db.execute.call_args.args[0]
    conditions = {clause.left.key: clause.right.value for clause in statement.whereclause.clauses}
    assert conditions == {
        "source_template_id": source,
        "source_tenant": "acme",
        "status": [TemplateStatus.APPROVED],
        "is_deleted": 0,
    }
    assert statement.table.name == "templates"


@pytest.mark.asyncio
async def test_only_the_authors_own_rejected_template_carries_the_reason():
    user = uuid4()
    rejected, resubmitted, unpublished = _row("Rejected"), _row("Resubmitted"), _row("Unpublished")
    mine = {"source_tenant": TENANT}
    master = AsyncMock()
    # Newest first: the resubmitted template's latest copy is pending, so no reason shows, even a stale one.
    # A copy from another tenant with the same template id is ignored.
    master.published_by_user.return_value = [
        _row("copy", source_template_id=rejected.id, status=TemplateStatus.APPROVED, source_tenant="other",
             rejection_reason=None),
        _row("copy", source_template_id=resubmitted.id, status=TemplateStatus.PENDING, rejection_reason="Stale", **mine),
        _row("copy", source_template_id=rejected.id, status=TemplateStatus.REJECTED, rejection_reason="Too vague",
             **mine),
        _row("copy", source_template_id=resubmitted.id, status=TemplateStatus.REJECTED, rejection_reason="Old", **mine),
    ]
    community = _row("Community", source_tenant="other", source_template_id=uuid4(), rejection_reason="Stale")
    master.list_by_status.return_value = [community]
    service = _service(master)
    service.repository.list_for_user.return_value = [rejected, resubmitted, unpublished]

    items = {item.title: item for item in await service.list_templates(user)}

    assert (items["Rejected"].publish_status, items["Rejected"].rejection_reason) == ("rejected", "Too vague")
    assert (items["Resubmitted"].publish_status, items["Resubmitted"].rejection_reason) == ("pending", None)
    assert (items["Unpublished"].publish_status, items["Unpublished"].rejection_reason) == (None, None)
    assert items["Community"].is_global and items["Community"].rejection_reason is None


@pytest.mark.asyncio
async def test_the_review_queue_carries_no_rejection_reason():
    master = AsyncMock()
    master.list_by_status.return_value = [_row("Pending", rejection_reason="Old")]

    (item,) = await _service(master).list_pending()

    assert item.rejection_reason is None


def test_a_full_template_response_never_carries_the_reason():
    read = TemplateRead(id=uuid4(), title="Shared", graph={}, rejection_reason="Too vague")
    assert "rejection_reason" not in read.model_dump()
    assert "rejection_reason" not in read.model_dump(mode="json")


@pytest.mark.asyncio
async def test_publish_takes_the_same_row_lock_as_delete():
    user = uuid4()
    private = _private(user)
    vars(private).update(
        title="Support", description=None, category=None, icon=None, tags=[], node_types=[],
        graph={"nodes": [], "edges": []}, agent_config=None,
    )
    master = AsyncMock()
    master.find_published.return_value = None

    def created(copy):
        # What the database fills in on insert.
        copy.id, copy.install_count = uuid4(), 0
        return copy

    master.create.side_effect = created
    service = _service(master, private)

    await service.publish(private.id, user)

    service.repository.get_locked.assert_awaited_once_with(private.id)
    service.repository.get_by_id.assert_not_awaited()


@pytest.mark.asyncio
async def test_the_lock_reads_the_row_fresh():
    db = MagicMock()
    db.execute = AsyncMock(return_value=MagicMock())

    await TemplateRepository(db).get_locked(uuid4())

    statement = db.execute.call_args.args[0]
    assert statement._for_update_arg is not None
    # A row already loaded in the session is refreshed, so the check after the wait sees the committed state.
    assert statement.get_execution_options().get("populate_existing") is True
