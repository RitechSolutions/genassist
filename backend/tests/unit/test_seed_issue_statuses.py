"""Unit tests for seeding the default issue statuses on new tenants and cold starts"""

from unittest.mock import AsyncMock

import pytest
from sqlalchemy.dialects import postgresql

from app.core.utils.enums.issue_status_enum import DEFAULT_ISSUE_STATUSES
from app.db.seed.seed import seed_issue_statuses


class FakeSession:
    def __init__(self):
        self.statements = []
        self.commit = AsyncMock()

    async def execute(self, stmt):
        self.statements.append(stmt)


@pytest.mark.asyncio
async def test_each_default_status_is_inserted_once_and_idempotently():
    session = FakeSession()
    await seed_issue_statuses(session)

    assert len(session.statements) == len(DEFAULT_ISSUE_STATUSES)
    for stmt in session.statements:
        assert "ON CONFLICT ON CONSTRAINT uq_issue_statuses_key DO NOTHING" in str(
            stmt.compile(dialect=postgresql.dialect())
        )
    session.commit.assert_awaited_once()
