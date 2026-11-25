"""Unit tests for the shape of the analytics aggregation statements"""

import asyncio
from datetime import date, datetime, timezone
from uuid import uuid4

from sqlalchemy.dialects import postgresql

import app.db.models.test_suite  # noqa: F401  # mapper config needs TestSuiteModel registered
from app.db.events.group_scope import GROUP_SCOPE_BYPASS_FLAG
from app.db.events.soft_delete import SOFT_DELETE_FLAG
from app.repositories.analytics_aggregation import AnalyticsAggregationRepository, ExecutionDelta, StatsDelta

AGENT_ID = uuid4()
STAT_DATE = date(2026, 7, 1)
SINCE = datetime(2026, 6, 30, 2, 0, tzinfo=timezone.utc)
UNTIL = datetime(2026, 7, 1, 14, 0, tzinfo=timezone.utc)
STAMPED_AT = datetime(2026, 7, 1, 14, 5, tzinfo=timezone.utc)


class CapturingSession:
    def __init__(self):
        self.statements = []

    async def execute(self, stmt):
        self.statements.append(stmt)

    async def commit(self):
        pass

    async def flush(self):
        pass


class _StubResult:
    rowcount = 0

    def all(self):
        return []

    def scalars(self):
        return self


class RecordingSession(CapturingSession):
    async def execute(self, stmt):
        self.statements.append(stmt)
        return _StubResult()


def _capture(coro) -> list:
    session = RecordingSession()
    repo = AnalyticsAggregationRepository(db=session)
    asyncio.run(coro(repo))
    return session.statements


def _compiled(stmt):
    return stmt.compile(dialect=postgresql.dialect())


def _set_clause(sql: str) -> str:
    return sql.split(" set ", 1)[1].split(" where ", 1)[0]


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

    def test_conflict_revives_a_soft_deleted_row(self):
        assert "is_deleted = excluded.is_deleted" in _rendered_upsert()

    def test_timing_columns_are_still_cleared_by_null(self):
        sql = _rendered_upsert()
        assert "avg_response_ms = coalesce" not in sql
        assert "total_response_ms = coalesce" not in sql


class TestRealtimeDeltaUpserts:
    def _agent_sql(self, delta):
        statements = _capture(lambda repo: repo.increment_agent_daily_stats(AGENT_ID, STAT_DATE, delta))
        compiled = _compiled(statements[0])
        return str(compiled).lower(), compiled.params

    def _node_statements(self, nodes):
        return _capture(lambda repo: repo.increment_node_daily_stats(AGENT_ID, STAT_DATE, nodes))

    def test_in_progress_clamps_once_on_the_net_change(self):
        sql, params = self._agent_sql(StatsDelta(starts=1, finalizes=3))
        assert params["in_progress_conversations"] == 0
        assert "in_progress_conversations = greatest(agent_execution_daily_stats.in_progress_conversations + " in sql
        assert params["in_progress_conversations_1"] == -2

    def test_average_keeps_untimed_runs_in_the_denominator(self):
        delta = StatsDelta()
        for ms in (100.0, 200.0, None):
            delta.add(True, ms)
        sql, params = self._agent_sql(delta)
        assert params["avg_response_ms"] == 100.0
        assert "/ cast((agent_execution_daily_stats.execution_count + %(execution_count_1)s)" in sql
        assert params["execution_count_1"] == 3

    def test_only_deltas_with_executions_write_tokens_and_move_the_watermark(self):
        conversation_sql, conversation_params = self._agent_sql(StatsDelta(starts=1))
        reply = StatsDelta()
        reply.add(True, None)
        reply_sql, _ = self._agent_sql(reply)

        for column in ("total_input_tokens", "total_cost_usd", "avg_response_ms", "last_aggregated_at"):
            assert f"{column} =" not in conversation_sql.split(" do update set ", 1)[1]
        assert "total_input_tokens" not in conversation_params
        assert "total_input_tokens = (coalesce(agent_execution_daily_stats.total_input_tokens" in reply_sql
        assert "last_aggregated_at = excluded.last_aggregated_at" in reply_sql

    def test_node_types_go_out_as_one_statement(self):
        nodes = {"llmNode": ExecutionDelta(), "toolNode": ExecutionDelta()}
        nodes["llmNode"].add(True, 50.0)
        nodes["toolNode"].add(False, None)
        statements = self._node_statements(nodes)
        assert len(statements) == 1
        compiled = _compiled(statements[0])
        assert [compiled.params["node_type_m0"], compiled.params["node_type_m1"]] == ["llmNode", "toolNode"]
        assert "on conflict on constraint uq_node_execution_daily_stats_agent_node_date" in str(compiled).lower()

    def test_untimed_node_types_keep_their_stored_timing(self):
        nodes = {"toolNode": ExecutionDelta()}
        nodes["toolNode"].add(True, None)
        sql = str(_compiled(self._node_statements(nodes)[0])).lower()
        assert (
            "total_execution_ms = case when (excluded.total_execution_ms is null) "
            "then node_execution_daily_stats.total_execution_ms" in sql
        )
        assert (
            "avg_execution_ms = case when (excluded.total_execution_ms is null) "
            "then node_execution_daily_stats.avg_execution_ms" in sql
        )


class TestLogPaginationOrdering:
    def test_per_date_paging_orders_by_a_unique_key(self):
        statements = _capture(lambda repo: repo.get_response_logs_for_date(STAT_DATE))
        sql = str(_compiled(statements[0])).lower()
        assert "order by agent_response_logs.logged_at, agent_response_logs.id" in sql

    def test_windowed_paging_orders_by_a_unique_key(self):
        statements = _capture(lambda repo: repo.get_response_logs_since(SINCE, UNTIL))
        sql = str(_compiled(statements[0])).lower()
        assert "order by agent_response_logs.logged_at, agent_response_logs.id" in sql


class TestDiscoveryStatementShape:
    def _statement(self):
        statements = _capture(lambda repo: repo.discover_affected_dates(SINCE, UNTIL))
        assert len(statements) == 1
        return statements[0]

    def test_all_four_sources_ride_one_union(self):
        assert str(_compiled(self._statement())).lower().count(" union ") == 3

    def test_union_bypasses_both_listener_filters(self):
        options = self._statement().get_execution_options()
        assert options.get(SOFT_DELETE_FLAG) is True
        assert options.get(GROUP_SCOPE_BYPASS_FLAG) is True

    def test_every_source_truncates_in_explicit_utc(self):
        compiled = _compiled(self._statement())
        assert str(compiled).lower().count("cast(timezone(") == 4
        assert list(compiled.params.values()).count("UTC") == 3

    def test_log_sources_keep_the_explicit_is_deleted_predicate(self):
        assert str(_compiled(self._statement())).lower().count("agent_response_logs.is_deleted = ") == 3

    def test_logless_source_anti_joins_and_coalesces_creation_date(self):
        sql = str(_compiled(self._statement())).lower()
        assert "not (exists" in sql
        assert "coalesce(conversations.conversation_date, conversations.created_at)" in sql


class TestLegacyAffectedDatesUtcAlignment:
    def test_selection_truncates_in_explicit_utc(self):
        statements = _capture(lambda repo: repo.get_affected_dates_since(SINCE, UNTIL))
        compiled = _compiled(statements[0])
        sql = str(compiled).lower()
        assert "cast(timezone(" in sql
        assert "date(agent_response_logs.logged_at)" not in sql
        assert list(compiled.params.values()).count("UTC") == 1


class TestAggregationStateUpsert:
    def test_cursor_advance_is_greatest_monotonic_on_the_singleton_constraint(self):
        statements = _capture(lambda repo: repo.upsert_aggregation_state(STAMPED_AT))
        sql = str(_compiled(statements[0])).lower()
        assert "on conflict on constraint uq_analytics_aggregation_state_key" in sql
        assert "greatest(analytics_aggregation_state.last_incremental_run_at, excluded.last_incremental_run_at)" in sql


class TestAgentReconciliationShape:
    def _statements(self):
        return _capture(lambda repo: repo.reconcile_agent_daily_stats(STAT_DATE, [AGENT_ID], STAMPED_AT))

    def test_soft_delete_targets_only_active_cost_free_absent_rows(self):
        compiled = _compiled(self._statements()[0])
        sql = str(compiled).lower()
        assert sql.startswith("update agent_execution_daily_stats")
        assert "agent_execution_daily_stats.is_deleted = " in sql and compiled.params["is_deleted_1"] == 0
        for column in ("total_input_tokens", "total_output_tokens", "total_cost_usd"):
            assert f"coalesce(agent_execution_daily_stats.{column}" in sql
        assert "not in" in sql

    def test_soft_delete_flips_the_flag_and_stamps_nothing_else(self):
        compiled = _compiled(self._statements()[0])
        assert _set_clause(str(compiled).lower()) == "updated_at=%(updated_at)s, is_deleted=%(is_deleted)s"
        assert compiled.params["is_deleted"] == 1
        assert compiled.params["updated_at"] == STAMPED_AT

    def test_zeroing_never_touches_the_token_and_cost_trio(self):
        sql = str(_compiled(self._statements()[1])).lower()
        assert sql.startswith("update agent_execution_daily_stats")
        assert "agent_execution_daily_stats.is_deleted = " in sql, "hidden rows must stay out of the zeroing"
        for column in ("total_input_tokens", "total_output_tokens", "total_cost_usd"):
            assert column not in sql

    def test_zeroing_stamps_timestamps_and_nulls_timings(self):
        params = _compiled(self._statements()[1]).params
        assert params["last_aggregated_at"] == STAMPED_AT
        assert params["updated_at"] == STAMPED_AT
        for column in ("avg_response_ms", "min_response_ms", "max_response_ms", "total_response_ms"):
            assert params[column] is None
        for column in ("execution_count", "unique_conversations", "thumbs_up_count"):
            assert params[column] == 0


class TestNodeReconciliationShape:
    def _statement(self):
        statements = _capture(
            lambda repo: repo.reconcile_node_daily_stats(STAT_DATE, [(AGENT_ID, "apiToolNode")], STAMPED_AT)
        )
        return _compiled(statements[0])

    def test_soft_delete_excludes_present_keys_by_tuple(self):
        compiled = self._statement()
        sql = str(compiled).lower()
        assert sql.startswith("update node_execution_daily_stats")
        assert "node_execution_daily_stats.is_deleted = " in sql and compiled.params["is_deleted_1"] == 0
        assert "(node_execution_daily_stats.agent_id, node_execution_daily_stats.node_type)" in sql
        assert "not in" in sql

    def test_soft_delete_flips_the_flag_and_stamps_nothing_else(self):
        compiled = self._statement()
        assert _set_clause(str(compiled).lower()) == "updated_at=%(updated_at)s, is_deleted=%(is_deleted)s"
        assert compiled.params["is_deleted"] == 1
        assert compiled.params["updated_at"] == STAMPED_AT


class TestStatsOnlyDates:
    def test_bounds_apply_independently_per_source(self):
        statements = _capture(lambda repo: repo.get_stats_only_dates(STAT_DATE, None))
        assert len(statements) == 2
        for stmt in statements:
            sql = str(_compiled(stmt)).lower()
            assert "select distinct" in sql
            assert "stat_date >= " in sql
            assert "stat_date <= " not in sql

    def test_unbounded_backfill_scans_both_stats_tables_whole(self):
        statements = _capture(lambda repo: repo.get_stats_only_dates(None, None))
        rendered = [str(_compiled(stmt)).lower() for stmt in statements]
        assert any("agent_execution_daily_stats" in sql for sql in rendered)
        assert any("node_execution_daily_stats" in sql for sql in rendered)
        for sql in rendered:
            assert "stat_date >= " not in sql and "stat_date <= " not in sql


class TestCalendarSweep:
    def _sweep(self, cursor_date, today):
        return AnalyticsAggregationRepository(db=RecordingSession()).get_calendar_sweep_dates(cursor_date, today)

    def test_no_state_row_seeds_only_yesterday_and_today(self):
        assert self._sweep(None, STAT_DATE) == [date(2026, 6, 30), STAT_DATE]

    def test_cursor_range_is_inclusive_of_both_ends(self):
        assert self._sweep(date(2026, 6, 28), STAT_DATE) == [
            date(2026, 6, 28),
            date(2026, 6, 29),
            date(2026, 6, 30),
            STAT_DATE,
        ]

    def test_same_day_cursor_selects_only_today(self):
        assert self._sweep(STAT_DATE, STAT_DATE) == [STAT_DATE]
