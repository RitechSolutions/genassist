"""Regression tests: conversation search combined with filters that join the analysis table"""

import re

import pytest
from sqlalchemy.dialects import postgresql

# Register every mapper before a statement is compiled.
import app.db.models  # noqa: F401
import app.db.models.test_suite  # noqa: F401
from app.core.utils.enums.sentiment_enum import Sentiment
from app.core.utils.enums.sort_field_enum import SortField
from app.repositories.conversations_read import ANALYSIS_SCORE_FIELDS, ConversationReadRepository
from app.schemas.filter import ConversationFilter


class _Result:
    def unique(self):
        return self

    def scalars(self):
        return self

    def all(self):
        return []

    def scalar_one(self):
        return 0


class CapturingDb:

    def __init__(self):
        self.statements = []

    async def execute(self, stmt):
        self.statements.append(stmt)
        return _Result()


def _sql(stmt) -> str:
    return str(stmt.compile(dialect=postgresql.dialect()))


def _repo():
    db = CapturingDb()
    return ConversationReadRepository(db), db


def _filter(**values) -> ConversationFilter:
    # The list fields default to FastAPI Query objects that only resolve under Depends().
    return ConversationFilter(conversation_status=None, conversation_topics=None, **values)


async def _list(repo, conversation_filter):
    return await repo.fetch_conversations_with_relations(conversation_filter, include_messages=False)


async def _count(repo, conversation_filter):
    return await repo.count_conversations(conversation_filter)


def _assert_correlated_exists(sql: str, table: str):
    """The EXISTS keeps its own FROM and is tied to the outer conversation row"""
    correlation = rf"(conversations\.id = {table}\.conversation_id|{table}\.conversation_id = conversations\.id)"
    pattern = rf"EXISTS \(SELECT [^()]*?\s+FROM {table}\s+WHERE {correlation}"
    assert re.search(pattern, sql), sql


SENTIMENT_FILTER = {
    "sentiment": Sentiment.NEGATIVE,
    "hostility_positive_max": 3,
    "hostility_neutral_max": 6,
}

ANALYSIS_JOIN_FILTERS = [
    pytest.param(SENTIMENT_FILTER, id="sentiment"),
    *[
        pytest.param({f"{field}_min": 2, f"{field}_max": 8}, id=f"{field}-range")
        for field in sorted(ANALYSIS_SCORE_FIELDS)
    ],
    *[
        pytest.param({"order_by": SortField(field)}, id=f"order-by-{field}")
        for field in sorted(ANALYSIS_SCORE_FIELDS)
    ],
]

REPOSITORY_CALLS = [pytest.param(_list, id="list"), pytest.param(_count, id="count")]


@pytest.mark.asyncio
@pytest.mark.parametrize("repository_call", REPOSITORY_CALLS)
@pytest.mark.parametrize("analysis_filter", ANALYSIS_JOIN_FILTERS)
async def test_search_with_analysis_join_keeps_correlated_subquery(repository_call, analysis_filter):
    repo, db = _repo()

    await repository_call(repo, _filter(search="refund", **analysis_filter))

    sql = _sql(db.statements[0])
    assert "LEFT OUTER JOIN conversation_analysis" in sql
    _assert_correlated_exists(sql, "conversation_analysis")


@pytest.mark.asyncio
async def test_email_with_analysis_join_keeps_correlated_subquery():
    repo, db = _repo()

    await _list(repo, _filter(email="customer@example.com", **SENTIMENT_FILTER))

    sql = _sql(db.statements[0])
    assert "LEFT OUTER JOIN conversation_analysis" in sql
    _assert_correlated_exists(sql, "transcript_messages")


@pytest.mark.asyncio
async def test_search_alone_keeps_correlated_subqueries():
    repo, db = _repo()

    await _list(repo, _filter(search="refund"))

    sql = _sql(db.statements[0])
    assert "LEFT OUTER JOIN conversation_analysis" not in sql
    _assert_correlated_exists(sql, "conversation_analysis")
    _assert_correlated_exists(sql, "transcript_messages")
