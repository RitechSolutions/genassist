"""Unit tests asserting that supervised-group assignments require the supervisor role"""

from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql

import app.db.models  # noqa: F401 — registers mappers for ORM compilation
import app.db.models.test_suite  # noqa: F401
from app.auth.utils import authorized_supervised_group_ids
from app.repositories.notification import NotificationRepository
from app.repositories.user_groups import UserGroupRepository
from app.services import user_groups as user_groups_service
from app.services.user_groups import UserGroupService


class _Result:
    def scalars(self):
        return self

    def all(self):
        return []


class CapturingDb:
    def __init__(self):
        self.statements = []

    async def execute(self, stmt):
        self.statements.append(stmt)
        return _Result()


def _sql(stmt) -> str:
    return str(stmt.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))


def _user(*role_names, supervised=()):
    return SimpleNamespace(
        roles=[SimpleNamespace(name=name) for name in role_names],
        supervised_group_ids=list(supervised),
    )


def test_stale_assignments_are_dropped_once_the_supervisor_role_is_gone():
    assert authorized_supervised_group_ids(_user("operator", supervised=[uuid4()])) == []


def test_a_supervisor_keeps_their_assignments():
    supervised = [uuid4(), uuid4()]
    assert authorized_supervised_group_ids(_user("supervisor", supervised=supervised)) == supervised


@pytest.mark.parametrize(
    "principal",
    [None, SimpleNamespace(id=uuid4()), _user("supervisor")],
    ids=["no user", "api-key principal", "supervisor with no assignments"],
)
def test_principals_without_assignments_resolve_to_an_empty_scope(principal):
    assert authorized_supervised_group_ids(principal) == []


@pytest.mark.asyncio
async def test_group_supervisor_read_requires_the_role():
    db = CapturingDb()
    group_id = uuid4()
    await UserGroupRepository(db).get_supervisor_user_ids(group_id)

    sql = _sql(db.statements[0])
    assert "roles.name = 'supervisor'" in sql
    assert f"user_supervised_groups.group_id = '{group_id}'" in sql


def _notification_repo(monkeypatch, db, target_group_id):
    notification_type = SimpleNamespace(
        id=uuid4(),
        type="conversation_started",
        is_enabled=True,
        is_tenant=False,
        allow_all_tenant_users=False,
    )
    repo = NotificationRepository(db)

    async def _types():
        return {notification_type.type: notification_type}

    async def _recipients(type_ids):
        return {}, {notification_type.id: {target_group_id}}

    monkeypatch.setattr(repo, "ensure_notification_types", _types)
    monkeypatch.setattr(repo, "_recipients_by_type_id", _recipients)
    return repo


def _statement_matching(db, needle: str) -> str:
    matches = [sql for sql in map(_sql, db.statements) if needle in sql]
    assert len(matches) == 1, f"expected exactly one statement touching {needle}"
    return matches[0]


@pytest.mark.asyncio
async def test_notification_delivery_only_reaches_users_who_still_supervise(monkeypatch):
    db = CapturingDb()
    group_id = uuid4()
    await _notification_repo(monkeypatch, db, group_id).resolve_recipient_user_ids(
        type_key="conversation_started", group_id=group_id
    )

    targeted = _statement_matching(db, "user_supervised_groups.group_id IN")
    assert "roles.name = 'supervisor'" in targeted

    retained = _statement_matching(db, f"user_supervised_groups.group_id = '{group_id}'")
    assert "roles.name = 'supervisor'" in retained


class _StubUserGroupRepository:

    def __init__(self, *, already_supervisor: bool):
        self.already_supervisor = already_supervisor
        self.added = []
        self.removed = []

    async def get_by_id(self, group_id):
        return SimpleNamespace(id=group_id)

    async def user_has_supervisor_role(self, user_id):
        return True

    async def is_supervisor(self, group_id, user_id):
        return self.already_supervisor

    async def add_supervisor(self, group_id, user_id):
        self.added.append((group_id, user_id))

    async def remove_supervisor(self, group_id, user_id):
        self.removed.append((group_id, user_id))


@pytest.fixture
def invalidated(monkeypatch):
    calls = []

    async def _record(user_id):
        calls.append(user_id)

    monkeypatch.setattr(user_groups_service, "invalidate_user_cache", _record)
    return calls


@pytest.mark.asyncio
@pytest.mark.parametrize("already_supervisor", [False, True], ids=["new", "already assigned"])
async def test_adding_a_supervisor_invalidates_their_auth_cache(invalidated, already_supervisor):
    user_id = uuid4()
    service = UserGroupService(_StubUserGroupRepository(already_supervisor=already_supervisor))
    await service.add_supervisor(uuid4(), user_id)

    assert invalidated == [user_id]


@pytest.mark.asyncio
async def test_removing_a_supervisor_invalidates_their_auth_cache(invalidated):
    user_id = uuid4()
    service = UserGroupService(_StubUserGroupRepository(already_supervisor=True))
    await service.remove_supervisor(uuid4(), user_id)

    assert invalidated == [user_id]
