"""DB-backed proof that the operator list paginates, orders and searches in SQL"""

import decimal
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config.settings import settings
from app.db.models import (
    OperatorModel,
    OperatorStatisticsModel,
    UserModel,
    UserTypeModel,
    test_suite,  # noqa: F401
)
from app.repositories.operators import OperatorRepository
from app.schemas.filter import OperatorListFilter

RANKED_COUNT = 21
MATCHING_COUNT = RANKED_COUNT + 4
TURKISH_NAME = "İlkay"


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine(settings.DATABASE_URL)
    maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as session:
        yield session
    await engine.dispose()


async def _add_operator(session, *, user_id, first_name, last_name, sentiment, score, is_deleted=0, stats_deleted=0):
    stats = OperatorStatisticsModel(
        avg_positive_sentiment=sentiment,
        avg_negative_sentiment=0,
        avg_neutral_sentiment=0,
        score=decimal.Decimal(str(score)),
        call_count=0,
        is_deleted=stats_deleted,
    )
    session.add(stats)
    await session.flush()

    operator = OperatorModel(
        first_name=first_name,
        last_name=last_name,
        is_active=1,
        statistics_id=stats.id,
        user_id=user_id,
        is_deleted=is_deleted,
    )
    session.add(operator)
    await session.flush()
    return operator, stats


@pytest_asyncio.fixture
async def seeded_operators(db_session):
    session = db_session
    prefix = f"zz_{uuid4().hex[:8]}_"

    user_type_id = (await session.execute(select(UserTypeModel.id).limit(1))).scalar_one()
    user = UserModel(
        username=f"{prefix}user",
        email=f"{prefix}user@example.test",
        hashed_password="not-a-real-hash",
        is_active=1,
        user_type_id=user_type_id,
    )
    session.add(user)
    await session.flush()

    operator_ids, stats_ids, tied_ids = [], [], []
    try:
        for i in range(RANKED_COUNT):
            operator, stats = await _add_operator(
                session,
                user_id=user.id,
                first_name=f"{prefix}op{i:02d}",
                last_name=f"{prefix}last{i:02d}",
                sentiment=90 - (i // 2),
                score=100 - i,
            )
            operator_ids.append(operator.id)
            stats_ids.append(stats.id)

        tied_names = (
            f"{prefix}be%ta",
            f"{prefix}back\\slash",
            f"{prefix}{TURKISH_NAME}",
            f"{prefix}tie",
        )
        for name in tied_names:
            tied, tied_stats = await _add_operator(
                session,
                user_id=user.id,
                first_name=name,
                last_name=f"{prefix}probe",
                sentiment=0,
                score=0,
            )
            operator_ids.append(tied.id)
            stats_ids.append(tied_stats.id)
            tied_ids.append(tied.id)

        deleted, deleted_stats = await _add_operator(
            session,
            user_id=user.id,
            first_name=f"{prefix}op99",
            last_name=f"{prefix}gone",
            sentiment=100,
            score=200,
            is_deleted=1,
        )
        operator_ids.append(deleted.id)
        stats_ids.append(deleted_stats.id)

        orphan, orphan_stats = await _add_operator(
            session,
            user_id=user.id,
            first_name=f"{prefix}op98",
            last_name=f"{prefix}orphan",
            sentiment=95,
            score=150,
            stats_deleted=1,
        )
        operator_ids.append(orphan.id)
        stats_ids.append(orphan_stats.id)

        await session.commit()
        session.expunge_all()

        yield {
            "prefix": prefix,
            "deleted_id": deleted.id,
            "orphan_id": orphan.id,
            "operator_ids": operator_ids,
            "tied_ids": tied_ids,
            "visible_ids": set(operator_ids) - {deleted.id, orphan.id},
        }
    finally:
        await session.execute(delete(OperatorModel).where(OperatorModel.id.in_(operator_ids)))
        await session.execute(delete(OperatorStatisticsModel).where(OperatorStatisticsModel.id.in_(stats_ids)))
        await session.execute(delete(UserModel).where(UserModel.id == user.id))
        await session.commit()


@pytest.mark.asyncio
async def test_total_counts_matching_rows_and_excludes_soft_deleted(db_session, seeded_operators):
    repo = OperatorRepository(db_session)
    prefix = seeded_operators["prefix"]

    rows, total = await repo.get_list_paginated(OperatorListFilter(skip=0, limit=100, search=prefix))

    assert total == MATCHING_COUNT
    assert len(rows) == MATCHING_COUNT
    assert seeded_operators["deleted_id"] not in {op.id for op in rows}


@pytest.mark.asyncio
async def test_soft_deleted_statistics_leave_count_and_rows_in_step(db_session, seeded_operators):
    repo = OperatorRepository(db_session)
    prefix = seeded_operators["prefix"]

    rows, total = await repo.get_list_paginated(OperatorListFilter(skip=0, limit=100, search=prefix))

    assert seeded_operators["orphan_id"] not in {op.id for op in rows}
    assert total == len(rows)


@pytest.mark.asyncio
async def test_database_returns_only_the_requested_page(db_session, seeded_operators):
    repo = OperatorRepository(db_session)
    prefix = seeded_operators["prefix"]

    page1, total1 = await repo.get_list_paginated(OperatorListFilter(skip=0, limit=20, search=prefix))
    page2, total2 = await repo.get_list_paginated(OperatorListFilter(skip=20, limit=20, search=prefix))

    assert len(page1) == 20
    assert len(page2) == MATCHING_COUNT - 20
    assert total1 == total2 == MATCHING_COUNT  # total is unpaginated

    ids1, ids2 = {op.id for op in page1}, {op.id for op in page2}
    assert ids1.isdisjoint(ids2)
    assert ids1 | ids2 == seeded_operators["visible_ids"]


@pytest.mark.asyncio
async def test_ordering_is_sentiment_then_score_then_stable(db_session, seeded_operators):
    repo = OperatorRepository(db_session)
    prefix = seeded_operators["prefix"]

    rows, _ = await repo.get_list_paginated(OperatorListFilter(skip=0, limit=100, search=prefix))

    ranked = [f"{prefix}op{i:02d}" for i in range(RANKED_COUNT)]
    assert [op.first_name for op in rows[:RANKED_COUNT]] == ranked

    keys = [(op.operator_statistics.avg_positive_sentiment, op.operator_statistics.score) for op in rows]
    assert keys == sorted(keys, reverse=True)
    tail_ids = [op.id for op in rows[RANKED_COUNT:]]
    assert set(tail_ids) == set(seeded_operators["tied_ids"])
    assert tail_ids == sorted(tail_ids, reverse=True)


@pytest.mark.asyncio
async def test_statistics_are_eagerly_loaded(db_session, seeded_operators):
    repo = OperatorRepository(db_session)
    prefix = seeded_operators["prefix"]

    rows, _ = await repo.get_list_paginated(OperatorListFilter(skip=0, limit=5, search=prefix))
    assert all(op.operator_statistics is not None for op in rows)
    assert rows[0].operator_statistics.avg_positive_sentiment == 90


@pytest.mark.asyncio
async def test_search_narrows_on_either_name_and_ignores_case(db_session, seeded_operators):
    repo = OperatorRepository(db_session)
    prefix = seeded_operators["prefix"]

    by_first, total_first = await repo.get_list_paginated(OperatorListFilter(skip=0, limit=100, search=f"{prefix}op07"))
    assert total_first == 1 and by_first[0].first_name == f"{prefix}op07"

    _, total_last = await repo.get_list_paginated(OperatorListFilter(skip=0, limit=100, search=f"{prefix}last07"))
    assert total_last == 1

    _, total_upper = await repo.get_list_paginated(
        OperatorListFilter(skip=0, limit=100, search=f"{prefix}op07".upper())
    )
    assert total_upper == 1

    _, total_none = await repo.get_list_paginated(OperatorListFilter(skip=0, limit=100, search=f"{prefix}nope"))
    assert total_none == 0


@pytest.mark.asyncio
async def test_like_wildcards_in_the_search_term_stay_literal(db_session, seeded_operators):
    repo = OperatorRepository(db_session)
    prefix = seeded_operators["prefix"]

    literal, total_literal = await repo.get_list_paginated(
        OperatorListFilter(skip=0, limit=100, search=f"{prefix}be%t")
    )
    assert total_literal == 1 and literal[0].first_name == f"{prefix}be%ta"

    _, total_wildcard = await repo.get_list_paginated(OperatorListFilter(skip=0, limit=100, search=f"{prefix}op%7"))
    assert total_wildcard == 0

    _, total_underscore = await repo.get_list_paginated(OperatorListFilter(skip=0, limit=100, search=f"{prefix}op_7"))
    assert total_underscore == 0

    backslash, total_backslash = await repo.get_list_paginated(
        OperatorListFilter(skip=0, limit=100, search=f"{prefix}back\\slash")
    )
    assert total_backslash == 1 and backslash[0].first_name == f"{prefix}back\\slash"

    _, total_escape_eaten = await repo.get_list_paginated(
        OperatorListFilter(skip=0, limit=100, search=f"{prefix}backslash")
    )
    assert total_escape_eaten == 0


@pytest.mark.asyncio
async def test_search_casefolds_the_way_the_database_does(db_session, seeded_operators):
    repo = OperatorRepository(db_session)
    prefix = seeded_operators["prefix"]
    stored = f"{prefix}{TURKISH_NAME}"

    pasted, total_pasted = await repo.get_list_paginated(OperatorListFilter(skip=0, limit=100, search=stored))
    assert total_pasted == 1 and pasted[0].first_name == stored

    _, total_lower = await repo.get_list_paginated(OperatorListFilter(skip=0, limit=100, search=f"{prefix}ilkay"))
    assert total_lower == 1

    _, total_upper = await repo.get_list_paginated(OperatorListFilter(skip=0, limit=100, search=f"{prefix}ILKAY"))
    assert total_upper == 1


@pytest.mark.asyncio
async def test_blank_search_is_treated_as_no_search(db_session, seeded_operators):
    repo = OperatorRepository(db_session)

    _, total_blank = await repo.get_list_paginated(OperatorListFilter(skip=0, limit=1, search="   "))
    _, total_unset = await repo.get_list_paginated(OperatorListFilter(skip=0, limit=1))

    assert total_blank == total_unset >= MATCHING_COUNT
