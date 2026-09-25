"""PostgreSQL-backed proof that prompt saves survive races and deletions"""

import asyncio
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config.settings import settings
from app.core.exceptions.exception_classes import AppException
from app.db.models.prompt_editor import PromptConfigModel, PromptVersionModel
from app.db.models.workflow import WorkflowModel
from app.repositories.prompt_editor import PromptConfigRepository, PromptVersionRepository
from app.repositories.test_suite import TestCaseRepository, TestSuiteRepository
from app.repositories.workflow import WorkflowRepository
from app.schemas.prompt_editor import PromptVersionCreate
from app.services.prompt_editor import PromptEditorService

NODE_ID = "n1"
FIELD = "systemPrompt"
NODES = [{"id": NODE_ID, "type": "agentNode", "position": {"x": 0, "y": 0}, "data": {"name": "A"}}]


@pytest_asyncio.fixture
async def engine():
    engine = create_async_engine(settings.DATABASE_URL)
    try:
        async with engine.connect():
            pass
    except OSError as exc:
        await engine.dispose()
        pytest.skip(f"no dev database reachable: {exc}")
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def session_maker(engine):
    return sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture
async def workflow(session_maker):
    async with session_maker() as session:
        row = WorkflowModel(name=f"zz_pe_{uuid4().hex[:8]}", version="1", nodes=NODES)
        session.add(row)
        await session.commit()
    yield row
    async with session_maker() as session:
        await session.execute(
            delete(PromptVersionModel).where(PromptVersionModel.workflow_id == row.id)
        )
        await session.execute(
            delete(PromptConfigModel).where(PromptConfigModel.workflow_id == row.id)
        )
        await session.execute(delete(WorkflowModel).where(WorkflowModel.id == row.id))
        await session.commit()


def _service(session: AsyncSession) -> PromptEditorService:
    return PromptEditorService(
        version_repo=PromptVersionRepository(session),
        config_repo=PromptConfigRepository(session),
        suite_repo=TestSuiteRepository(session),
        case_repo=TestCaseRepository(session),
        workflow_repo=WorkflowRepository(session),
        db=session,
    )


async def _live_numbers(session_maker, workflow_id) -> list[int]:
    async with session_maker() as session:
        result = await session.execute(
            select(PromptVersionModel.version_number)
            .where(
                PromptVersionModel.workflow_id == workflow_id,
                PromptVersionModel.is_deleted == 0,
            )
            .order_by(PromptVersionModel.version_number)
        )
        return list(result.scalars().all())


@pytest.mark.asyncio
async def test_concurrent_first_configuration_creation_leaves_one_row(session_maker, workflow):
    async def create():
        async with session_maker() as session:
            row = await PromptConfigRepository(session).get_or_create(
                workflow.id, NODE_ID, FIELD
            )
            await session.commit()
            return row.id

    first, second = await asyncio.gather(create(), create())

    assert first == second
    async with session_maker() as session:
        result = await session.execute(
            select(PromptConfigModel.id).where(PromptConfigModel.workflow_id == workflow.id)
        )
        assert len(result.scalars().all()) == 1


@pytest.mark.asyncio
async def test_concurrent_saves_give_distinct_numbers_or_a_clean_409(session_maker, workflow):
    async def save(content: str):
        async with session_maker() as session:
            try:
                created = await _service(session).create_version(
                    workflow.id, NODE_ID, FIELD, PromptVersionCreate(content=content)
                )
            except AppException as exc:
                await session.rollback()
                return exc
            await session.commit()
            return created.version_number

    results = await asyncio.gather(save("a"), save("b"))

    assert len(results) == 2
    conflicts = [r for r in results if isinstance(r, AppException)]
    numbers = [r for r in results if not isinstance(r, AppException)]
    assert numbers, "a race must not lose both saves"
    assert all(exc.status_code == 409 for exc in conflicts)
    assert len(set(numbers)) == len(numbers)
    assert await _live_numbers(session_maker, workflow.id) == sorted(numbers)


@pytest.mark.asyncio
async def test_a_save_after_deleting_the_newest_version_never_reissues_its_number(
    session_maker, workflow
):
    async with session_maker() as session:
        service = _service(session)
        for content in ("v1", "v2", "v3"):
            await service.create_version(
                workflow.id, NODE_ID, FIELD, PromptVersionCreate(content=content)
            )
        await session.commit()

        newest = (
            await PromptVersionRepository(session).get_versions_for_context(
                workflow.id, NODE_ID, FIELD
            )
        )[0]
        assert newest.version_number == 3
        await service.delete_version(newest.id)
        await session.commit()

        created = await service.create_version(
            workflow.id, NODE_ID, FIELD, PromptVersionCreate(content="v4")
        )
        await session.commit()

    assert created.version_number == 4
    assert await _live_numbers(session_maker, workflow.id) == [1, 2, 4]

    async with session_maker() as session:
        history = await PromptVersionRepository(session).get_versions_for_context(
            workflow.id, NODE_ID, FIELD
        )
        assert [v.version_number for v in history] == [4, 2, 1]

        still_active = (
            await session.execute(
                select(PromptVersionModel.is_active)
                .execution_options(include_deleted=True)
                .where(PromptVersionModel.id == newest.id)
            )
        ).scalar_one()
        assert still_active is True
