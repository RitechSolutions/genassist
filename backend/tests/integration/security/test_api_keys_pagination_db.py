"""DB-backed proof that the API key list paginates, orders and searches in SQL"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config.settings import settings
from app.db.models import (
    ApiKeyModel,
    ApiKeyRoleModel,
    RoleModel,
    UserModel,
    UserTypeModel,
    test_suite,  # noqa: F401
)
from app.repositories.api_keys import ApiKeysRepository
from app.schemas.api_key import ApiKeySafeRead
from app.schemas.filter import ApiKeyListFilter, ApiKeysFilter

ORDERED_COUNT = 22
TIE_COUNT = 3
PROBE_NAMES = ("be%ta", "back\\slash", "İlkay")
MATCHING_COUNT = ORDERED_COUNT + TIE_COUNT + len(PROBE_NAMES)
TURKISH_NAME = PROBE_NAMES[2]
BASE_CREATED_AT = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine(settings.DATABASE_URL)
    maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as session:
        yield session
    await engine.dispose()


@pytest_asyncio.fixture
async def seeded_api_keys(db_session):
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

    role_id = (await session.execute(select(RoleModel.id).limit(1))).scalar_one()

    def add_key(name, created_at, is_deleted=0):
        key = ApiKeyModel(
            name=name,
            is_active=1,
            user_id=user.id,
            key_val="enc",
            hashed_value=f"{prefix}h_{name}",
            created_at=created_at,
            is_deleted=is_deleted,
        )
        session.add(key)
        return key

    key_ids = []
    try:
        ordered = [add_key(f"{prefix}key{i:02d}", BASE_CREATED_AT - timedelta(minutes=i)) for i in range(ORDERED_COUNT)]
        tied = [add_key(f"{prefix}tie{j}", BASE_CREATED_AT - timedelta(minutes=100)) for j in range(TIE_COUNT)]
        probes = [add_key(f"{prefix}{n}", BASE_CREATED_AT - timedelta(minutes=200 + j)) for j, n in enumerate(PROBE_NAMES)]
        deleted = add_key(f"{prefix}gone", BASE_CREATED_AT - timedelta(minutes=300), is_deleted=1)

        await session.flush()
        key_ids = [key.id for key in [*ordered, *tied, *probes, deleted]]
        with_role_id = ordered[0].id

        session.add(ApiKeyRoleModel(api_key_id=with_role_id, role_id=role_id))
        await session.commit()
        session.expunge_all()

        yield {
            "prefix": prefix,
            "user_id": user.id,
            "role_id": role_id,
            "with_role_id": with_role_id,
            "keyless_id": ordered[1].id,
            "deleted_id": deleted.id,
            "tied_ids": [key.id for key in tied],
            "visible_ids": set(key_ids) - {deleted.id},
        }
    finally:
        await session.execute(delete(ApiKeyRoleModel).where(ApiKeyRoleModel.api_key_id.in_(key_ids)))
        await session.execute(delete(ApiKeyModel).where(ApiKeyModel.id.in_(key_ids)))
        await session.execute(delete(UserModel).where(UserModel.id == user.id))
        await session.commit()


@pytest.mark.asyncio
async def test_total_counts_matching_rows_and_excludes_soft_deleted(db_session, seeded_api_keys):
    repo = ApiKeysRepository(db_session)
    prefix = seeded_api_keys["prefix"]

    rows, total = await repo.get_list_paginated(ApiKeyListFilter(skip=0, limit=100, search=prefix))

    assert total == MATCHING_COUNT
    assert len(rows) == MATCHING_COUNT
    assert {key.id for key in rows} == seeded_api_keys["visible_ids"]
    assert seeded_api_keys["deleted_id"] not in {key.id for key in rows}


@pytest.mark.asyncio
async def test_database_returns_only_the_requested_page(db_session, seeded_api_keys):
    repo = ApiKeysRepository(db_session)
    prefix = seeded_api_keys["prefix"]

    page1, total1 = await repo.get_list_paginated(ApiKeyListFilter(skip=0, limit=10, search=prefix))
    page2, total2 = await repo.get_list_paginated(ApiKeyListFilter(skip=10, limit=10, search=prefix))
    page3, total3 = await repo.get_list_paginated(ApiKeyListFilter(skip=20, limit=10, search=prefix))

    assert [len(page1), len(page2), len(page3)] == [10, 10, MATCHING_COUNT - 20]
    assert total1 == total2 == total3 == MATCHING_COUNT

    ids1, ids2, ids3 = ({key.id for key in page} for page in (page1, page2, page3))
    assert ids1.isdisjoint(ids2) and ids1.isdisjoint(ids3) and ids2.isdisjoint(ids3)
    assert ids1 | ids2 | ids3 == seeded_api_keys["visible_ids"]


@pytest.mark.asyncio
async def test_ordering_is_newest_first_and_stable_on_ties(db_session, seeded_api_keys):
    repo = ApiKeysRepository(db_session)
    prefix = seeded_api_keys["prefix"]

    rows, _ = await repo.get_list_paginated(ApiKeyListFilter(skip=0, limit=100, search=prefix))

    assert [key.name for key in rows[:ORDERED_COUNT]] == [f"{prefix}key{i:02d}" for i in range(ORDERED_COUNT)]

    timestamps = [key.created_at for key in rows]
    assert timestamps == sorted(timestamps, reverse=True)

    tie_ids = [key.id for key in rows[ORDERED_COUNT:ORDERED_COUNT + TIE_COUNT]]
    assert set(tie_ids) == set(seeded_api_keys["tied_ids"])
    assert tie_ids == sorted(seeded_api_keys["tied_ids"], reverse=True)


@pytest.mark.asyncio
async def test_roles_are_eagerly_loaded_for_serialisation(db_session, seeded_api_keys):
    repo = ApiKeysRepository(db_session)
    prefix = seeded_api_keys["prefix"]

    rows, _ = await repo.get_list_paginated(ApiKeyListFilter(skip=0, limit=100, search=prefix))
    by_id = {key.id: key for key in rows}

    with_role = ApiKeySafeRead.model_validate(by_id[seeded_api_keys["with_role_id"]])
    assert [role.id for role in with_role.roles] == [seeded_api_keys["role_id"]]
    assert "key_val" not in with_role.model_dump()

    keyless = ApiKeySafeRead.model_validate(by_id[seeded_api_keys["keyless_id"]])
    assert keyless.roles == []


@pytest.mark.asyncio
async def test_get_by_id_eagerly_loads_roles(db_session, seeded_api_keys):
    # Sole query in this test, so the role cannot already be in the identity map.
    repo = ApiKeysRepository(db_session)

    row = await repo.get_by_id(seeded_api_keys["with_role_id"])

    read = ApiKeySafeRead.model_validate(row)
    assert [role.id for role in read.roles] == [seeded_api_keys["role_id"]]


@pytest.mark.asyncio
async def test_legacy_get_all_eagerly_loads_roles(db_session, seeded_api_keys):
    repo = ApiKeysRepository(db_session)

    rows = await repo.get_all(ApiKeysFilter(skip=0, limit=100, user_id=seeded_api_keys["user_id"]))
    with_role = next(key for key in rows if key.id == seeded_api_keys["with_role_id"])

    read = ApiKeySafeRead.model_validate(with_role)
    assert [role.id for role in read.roles] == [seeded_api_keys["role_id"]]


@pytest.mark.asyncio
async def test_search_narrows_on_name_and_ignores_case(db_session, seeded_api_keys):
    repo = ApiKeysRepository(db_session)
    prefix = seeded_api_keys["prefix"]

    exact, total_exact = await repo.get_list_paginated(ApiKeyListFilter(skip=0, limit=100, search=f"{prefix}key07"))
    assert total_exact == 1 and exact[0].name == f"{prefix}key07"

    _, total_upper = await repo.get_list_paginated(
        ApiKeyListFilter(skip=0, limit=100, search=f"{prefix}key07".upper())
    )
    assert total_upper == 1

    _, total_none = await repo.get_list_paginated(ApiKeyListFilter(skip=0, limit=100, search=f"{prefix}nope"))
    assert total_none == 0


@pytest.mark.asyncio
async def test_like_wildcards_in_the_search_term_stay_literal(db_session, seeded_api_keys):
    repo = ApiKeysRepository(db_session)
    prefix = seeded_api_keys["prefix"]

    literal, total_literal = await repo.get_list_paginated(ApiKeyListFilter(skip=0, limit=100, search=f"{prefix}be%t"))
    assert total_literal == 1 and literal[0].name == f"{prefix}be%ta"

    _, total_wildcard = await repo.get_list_paginated(ApiKeyListFilter(skip=0, limit=100, search=f"{prefix}key%7"))
    assert total_wildcard == 0

    _, total_underscore = await repo.get_list_paginated(ApiKeyListFilter(skip=0, limit=100, search=f"{prefix}key_7"))
    assert total_underscore == 0

    backslash, total_backslash = await repo.get_list_paginated(
        ApiKeyListFilter(skip=0, limit=100, search=f"{prefix}back\\slash")
    )
    assert total_backslash == 1 and backslash[0].name == f"{prefix}back\\slash"

    _, total_escape_eaten = await repo.get_list_paginated(
        ApiKeyListFilter(skip=0, limit=100, search=f"{prefix}backslash")
    )
    assert total_escape_eaten == 0


@pytest.mark.asyncio
async def test_search_casefolds_the_way_the_database_does(db_session, seeded_api_keys):
    repo = ApiKeysRepository(db_session)
    prefix = seeded_api_keys["prefix"]
    stored = f"{prefix}{TURKISH_NAME}"

    pasted, total_pasted = await repo.get_list_paginated(ApiKeyListFilter(skip=0, limit=100, search=stored))
    assert total_pasted == 1 and pasted[0].name == stored

    _, total_lower = await repo.get_list_paginated(ApiKeyListFilter(skip=0, limit=100, search=f"{prefix}ilkay"))
    assert total_lower == 1

    _, total_upper = await repo.get_list_paginated(ApiKeyListFilter(skip=0, limit=100, search=f"{prefix}ILKAY"))
    assert total_upper == 1


@pytest.mark.asyncio
async def test_blank_search_is_treated_as_no_search(db_session, seeded_api_keys):
    repo = ApiKeysRepository(db_session)

    _, total_blank = await repo.get_list_paginated(ApiKeyListFilter(skip=0, limit=1, search="   "))
    _, total_unset = await repo.get_list_paginated(ApiKeyListFilter(skip=0, limit=1))

    assert total_blank == total_unset >= MATCHING_COUNT
