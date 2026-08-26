"""Integration tests for the supervisor-role transitions that own supervised-group rows"""

from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config.settings import settings
from app.db.models.role import RoleModel
from app.db.models.user import UserModel
from app.db.models.user_group import UserGroupModel
from app.db.models.user_role import UserRoleModel
from app.db.models.user_supervised_group import UserSupervisedGroupModel
from app.repositories.users import UserRepository
from app.schemas.user import UserUpdate


class World:
    def __init__(self, maker, user_id, group_ids, role_ids):
        self.maker = maker
        self.user_id = user_id
        self.group_ids = group_ids
        self.role_ids = role_ids

    async def supervised(self) -> set:
        async with self.maker() as session:
            rows = await session.execute(
                select(UserSupervisedGroupModel.group_id).where(UserSupervisedGroupModel.user_id == self.user_id)
            )
            return set(rows.scalars().all())

    async def grant_supervised(self, *group_ids):
        async with self.maker() as session:
            session.add_all(
                UserSupervisedGroupModel(id=uuid4(), user_id=self.user_id, group_id=gid) for gid in group_ids
            )
            await session.commit()

    async def update(self, **kwargs):
        async with self.maker() as session:
            await UserRepository(session).update(self.user_id, UserUpdate(**kwargs))
            await session.commit()


async def _skip_cache_clear(self, user_id):
    """FastAPI-Cache has no backend in the test harness — the repository would assert."""


@pytest_asyncio.fixture
async def world(app_def, monkeypatch):
    monkeypatch.setattr(UserRepository, "_clear_user_full_cache", _skip_cache_clear)

    engine = create_async_engine(settings.DATABASE_URL)
    maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    suffix = uuid4().hex[:12]
    user_id = uuid4()
    group_ids = [uuid4(), uuid4()]

    async with maker() as session:
        role_ids = {
            name: (await session.execute(select(RoleModel.id).where(RoleModel.name == name))).scalars().first()
            for name in ("supervisor", "operator")
        }
        assert all(role_ids.values()), "seeded supervisor/operator roles are required"

        user_type_id = (await session.execute(select(UserModel.user_type_id).limit(1))).scalar_one()
        session.add_all(UserGroupModel(id=gid, name=f"sglife-{gid.hex[:8]}", is_deleted=0) for gid in group_ids)
        session.add(
            UserModel(
                id=user_id,
                username=f"sglife-{suffix}",
                email=f"sglife-{suffix}@example.test",
                hashed_password="x",
                user_type_id=user_type_id,
                is_active=1,
                group_id=group_ids[0],
                is_deleted=0,
            )
        )
        await session.flush()
        session.add(UserRoleModel(id=uuid4(), user_id=user_id, role_id=role_ids["supervisor"]))
        session.add_all(UserSupervisedGroupModel(id=uuid4(), user_id=user_id, group_id=gid) for gid in group_ids)
        await session.commit()

    try:
        yield World(maker, user_id, group_ids, role_ids)
    finally:
        async with maker() as session:
            await session.execute(delete(UserSupervisedGroupModel).where(UserSupervisedGroupModel.user_id == user_id))
            await session.execute(delete(UserRoleModel).where(UserRoleModel.user_id == user_id))
            await session.execute(delete(UserModel).where(UserModel.id == user_id))
            await session.execute(delete(UserGroupModel).where(UserGroupModel.id.in_(group_ids)))
            await session.commit()
        await engine.dispose()


@pytest.mark.asyncio
async def test_keeping_the_supervisor_role_preserves_the_assignments(world):
    await world.update(role_ids=[world.role_ids["supervisor"], world.role_ids["operator"]])
    assert await world.supervised() == set(world.group_ids)


@pytest.mark.asyncio
async def test_losing_the_supervisor_role_drops_the_assignments(world):
    await world.update(role_ids=[world.role_ids["operator"]])
    assert await world.supervised() == set()


@pytest.mark.asyncio
async def test_re_promotion_does_not_reactivate_an_earlier_stints_assignments(world):
    await world.update(role_ids=[world.role_ids["operator"]])
    # Rows written before the cleanup shipped outlive the demotion that should have cleared them.
    await world.grant_supervised(*world.group_ids)
    await world.update(role_ids=[world.role_ids["supervisor"]])
    assert await world.supervised() == set()


@pytest.mark.asyncio
async def test_an_update_without_roles_leaves_the_assignments_untouched(world):
    await world.update(notes="unrelated edit")
    assert await world.supervised() == set(world.group_ids)
