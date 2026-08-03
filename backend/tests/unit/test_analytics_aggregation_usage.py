"""Unit tests for the shape of the agent daily-stats upsert"""

import asyncio
from datetime import date
from uuid import uuid4

from sqlalchemy.dialects import postgresql

from app.repositories.analytics_aggregation import AnalyticsAggregationRepository

AGENT_ID = uuid4()
STAT_DATE = date(2026, 7, 1)


class CapturingSession:
    def __init__(self):
        self.statements = []

    async def execute(self, stmt):
        self.statements.append(stmt)

    async def commit(self):
        pass


def _rendered_upsert() -> str:
    session = CapturingSession()
    repo = AnalyticsAggregationRepository(db=session)
    asyncio.run(
        repo.upsert_agent_daily_stats(
            [
                {
                    "agent_id": AGENT_ID,
                    "stat_date": STAT_DATE,
                    "execution_count": 1,
                    "success_count": 1,
                    "error_count": 0,
                    "total_nodes_executed": 2,
                    "rag_used_count": 0,
                    "unique_conversations": 1,
                }
            ]
        )
    )
    return str(session.statements[0].compile(dialect=postgresql.dialect())).lower()


class TestDailyStatsUpsert:
    def test_token_and_cost_columns_are_left_to_the_realtime_writer(self):
        sql = _rendered_upsert()
        for column in ("total_input_tokens", "total_output_tokens", "total_cost_usd"):
            assert column not in sql

    def test_every_other_column_still_overwrites(self):
        sql = _rendered_upsert()
        for column in ("execution_count", "avg_response_ms", "min_response_ms", "unique_conversations"):
            assert f"{column} = excluded.{column}" in sql

    def test_timing_columns_are_still_cleared_by_null(self):
        sql = _rendered_upsert()
        assert "avg_response_ms = coalesce" not in sql
        assert "total_response_ms = coalesce" not in sql
