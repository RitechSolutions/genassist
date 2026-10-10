"""DB-backed proof that the knowledge base list paginates, orders, searches and filters by type in SQL"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config.settings import settings
from app.db.models import KnowledgeBaseModel, test_suite  # noqa: F401
from app.repositories.knowledge_base import KnowledgeBaseRepository
from app.schemas.filter import KnowledgeBaseListFilter

ORDERED_COUNT = 12
TIE_COUNT = 2
MATCHING_COUNT = ORDERED_COUNT + TIE_COUNT + 2
BASE_CREATED_AT = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine(settings.DATABASE_URL)
    maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as session:
        yield session
    await engine.dispose()


@pytest_asyncio.fixture
async def seeded_knowledge_bases(db_session):
    session = db_session
    prefix = f"zz_{uuid4().hex[:8]}_"

    def add_kb(name, kb_type, created_at, description=None, is_deleted=0):
        kb = KnowledgeBaseModel(
            name=f"{prefix}{name}",
            type=kb_type,
            description=description,
            created_at=created_at,
            is_deleted=is_deleted,
        )
        session.add(kb)
        return kb

    kb_ids = []
    try:
        ordered = [
            add_kb(f"kb{i:02d}", "file" if i % 2 == 0 else "text", BASE_CREATED_AT - timedelta(minutes=i))
            for i in range(ORDERED_COUNT)
        ]
        tied = [add_kb(f"tie{j}", "url", BASE_CREATED_AT - timedelta(minutes=100)) for j in range(TIE_COUNT)]
        wildcard = add_kb("be%ta", "text", BASE_CREATED_AT - timedelta(minutes=200))
        described = add_kb(
            "described", "text", BASE_CREATED_AT - timedelta(minutes=201), description=f"About the {prefix}Needle"
        )
        deleted = add_kb("gone", "url", BASE_CREATED_AT - timedelta(minutes=300), is_deleted=1)

        await session.flush()
        kb_ids = [kb.id for kb in [*ordered, *tied, wildcard, described, deleted]]
        await session.commit()
        session.expunge_all()

        yield {
            "prefix": prefix,
            "deleted_id": deleted.id,
            "described_id": described.id,
            "tied_ids": [kb.id for kb in tied],
            "visible_ids": set(kb_ids) - {deleted.id},
        }
    finally:
        await session.rollback()
        await session.execute(delete(KnowledgeBaseModel).where(KnowledgeBaseModel.id.in_(kb_ids)))
        await session.commit()


@pytest.mark.asyncio
async def test_pages_are_disjoint_complete_and_exclude_soft_deleted(db_session, seeded_knowledge_bases):
    repo = KnowledgeBaseRepository(db_session)
    prefix = seeded_knowledge_bases["prefix"]

    page1, total1 = await repo.get_list_paginated(KnowledgeBaseListFilter(skip=0, limit=10, search=prefix))
    page2, total2 = await repo.get_list_paginated(KnowledgeBaseListFilter(skip=10, limit=10, search=prefix))

    assert [len(page1), len(page2)] == [10, MATCHING_COUNT - 10]
    assert total1 == total2 == MATCHING_COUNT

    ids1, ids2 = ({row.id for row in page} for page in (page1, page2))
    assert ids1.isdisjoint(ids2)
    assert ids1 | ids2 == seeded_knowledge_bases["visible_ids"]


@pytest.mark.asyncio
async def test_ordering_is_newest_first_and_stable_on_ties(db_session, seeded_knowledge_bases):
    repo = KnowledgeBaseRepository(db_session)
    prefix = seeded_knowledge_bases["prefix"]

    rows, _ = await repo.get_list_paginated(KnowledgeBaseListFilter(skip=0, limit=100, search=prefix))

    assert [row.name for row in rows[:ORDERED_COUNT]] == [f"{prefix}kb{i:02d}" for i in range(ORDERED_COUNT)]

    tie_ids = [row.id for row in rows[ORDERED_COUNT:ORDERED_COUNT + TIE_COUNT]]
    assert tie_ids == sorted(seeded_knowledge_bases["tied_ids"], reverse=True)

    assert [row.name for row in rows[ORDERED_COUNT + TIE_COUNT:]] == [f"{prefix}be%ta", f"{prefix}described"]


@pytest.mark.asyncio
async def test_search_matches_the_description_and_ignores_case(db_session, seeded_knowledge_bases):
    repo = KnowledgeBaseRepository(db_session)
    prefix = seeded_knowledge_bases["prefix"]

    rows, total = await repo.get_list_paginated(KnowledgeBaseListFilter(skip=0, limit=100, search=f"{prefix}NEEDLE"))

    assert total == 1
    assert [row.id for row in rows] == [seeded_knowledge_bases["described_id"]]


@pytest.mark.asyncio
async def test_like_wildcards_in_the_search_term_stay_literal(db_session, seeded_knowledge_bases):
    repo = KnowledgeBaseRepository(db_session)
    prefix = seeded_knowledge_bases["prefix"]

    literal, total_literal = await repo.get_list_paginated(
        KnowledgeBaseListFilter(skip=0, limit=100, search=f"{prefix}be%t")
    )
    assert total_literal == 1 and literal[0].name == f"{prefix}be%ta"

    _, total_wildcard = await repo.get_list_paginated(KnowledgeBaseListFilter(skip=0, limit=100, search=f"{prefix}k%0"))
    assert total_wildcard == 0


@pytest.mark.asyncio
async def test_type_filter_returns_only_that_type(db_session, seeded_knowledge_bases):
    repo = KnowledgeBaseRepository(db_session)
    prefix = seeded_knowledge_bases["prefix"]

    seeded_urls, total = await repo.get_list_paginated(
        KnowledgeBaseListFilter(skip=0, limit=100, search=prefix, type="url")
    )
    assert total == TIE_COUNT
    assert {row.id for row in seeded_urls} == set(seeded_knowledge_bases["tied_ids"])

    any_urls, _ = await repo.get_list_paginated(KnowledgeBaseListFilter(skip=0, limit=100, type="url"))
    assert any_urls and {row.type for row in any_urls} == {"url"}


@pytest.mark.asyncio
async def test_blank_search_and_type_are_treated_as_absent(db_session, seeded_knowledge_bases):
    repo = KnowledgeBaseRepository(db_session)

    _, total_blank = await repo.get_list_paginated(KnowledgeBaseListFilter(skip=0, limit=1, search="   ", type="  "))
    _, total_unset = await repo.get_list_paginated(KnowledgeBaseListFilter(skip=0, limit=1))

    assert total_blank == total_unset >= MATCHING_COUNT
