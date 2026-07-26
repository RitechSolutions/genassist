"""Per-day shadow reconciliation queries"""

from datetime import date, datetime
from decimal import Decimal

from injector import inject
from sqlalchemy import String, and_, cast, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.agent_execution_daily_stats import AgentExecutionDailyStatsModel
from app.db.models.agent_response_log import AgentResponseLogModel
from app.db.models.llm_usage import (
    LlmUsageCaptureRunModel,
    LlmUsageEventModel,
    LlmUsageReconciliationReportModel,
)
from app.repositories.db_repository import DbRepository

CHAT_SOURCE = "chat"
WORKFLOW_SOURCE_TYPE = "workflow"
ANALYST_SOURCE_TYPE = "llm_analyst"
RETURNED = "returned"
UNPRICED = "unpriced"

_LOG = AgentResponseLogModel
_RUN = LlmUsageCaptureRunModel
_EVENT = LlmUsageEventModel


def _chat_logs(start: datetime, end: datetime):
    return (
        _LOG.workflow_execution_id.isnot(None),
        _LOG.logged_at >= start,
        _LOG.logged_at < end,
        _LOG.is_deleted == 0,
    )


@inject
class LlmUsageReconciliationRepository(DbRepository[LlmUsageReconciliationReportModel]):
    """Per-day shadow reconciliation over the chat slice, joined by execution id"""

    def __init__(self, db: AsyncSession):
        super().__init__(LlmUsageReconciliationReportModel, db)

    # ── reports ────────────────────────────────────────────────
    async def recent_reports(self, limit: int) -> list[LlmUsageReconciliationReportModel]:
        """Most recent reports, newest day first."""
        result = await self.db.execute(
            select(LlmUsageReconciliationReportModel)
            .where(LlmUsageReconciliationReportModel.is_deleted == 0)
            .order_by(LlmUsageReconciliationReportModel.report_date.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def reports_between(self, from_date: date, to_date: date) -> list[LlmUsageReconciliationReportModel]:
        """Reports for an exact date range"""
        result = await self.db.execute(
            select(LlmUsageReconciliationReportModel)
            .where(
                LlmUsageReconciliationReportModel.is_deleted == 0,
                LlmUsageReconciliationReportModel.report_date >= from_date,
                LlmUsageReconciliationReportModel.report_date <= to_date,
            )
            .order_by(LlmUsageReconciliationReportModel.report_date)
            .execution_options(populate_existing=True)
        )
        return list(result.scalars().all())

    async def upsert_report(
        self,
        *,
        report_date: date,
        interval_start: datetime,
        interval_end: datetime,
        passed: bool,
        reasons: dict,
        metrics: dict,
    ) -> None:
        """Re-runs replace a prior report so repaired data can overwrite a failed day"""
        stmt = insert(LlmUsageReconciliationReportModel).values(
            report_date=report_date,
            interval_start=interval_start,
            interval_end=interval_end,
            passed=passed,
            reasons=reasons,
            metrics=metrics,
        )
        stmt = stmt.on_conflict_do_update(
            constraint="uq_llm_usage_reconciliation_reports_date",
            set_={
                "interval_start": interval_start,
                "interval_end": interval_end,
                "passed": passed,
                "reasons": reasons,
                "metrics": metrics,
                "is_deleted": 0,
            },
        )
        await self.db.execute(stmt)
        await self.db.commit()


    async def logs_without_receipts(self, start: datetime, end: datetime) -> list[str]:
        """Chat logs the recorder never wrote a receipt for"""
        stmt = (
            select(_LOG.workflow_execution_id)
            .outerjoin(
                _RUN,
                and_(_RUN.execution_id == _LOG.workflow_execution_id, _RUN.is_deleted == 0),
            )
            .where(*_chat_logs(start, end), _RUN.execution_id.is_(None))
        )
        return [row[0] for row in (await self.db.execute(stmt)).all()]

    async def recorder_integrity(self, start: datetime, end: datetime) -> tuple[int, list[dict]]:
        """Every workflow receipt against the events that actually landed"""
        event_counts = (
            select(_EVENT.execution_id, func.count().label("cnt"))
            .where(_EVENT.source_type == WORKFLOW_SOURCE_TYPE, _EVENT.is_deleted == 0)
            .group_by(_EVENT.execution_id)
            .subquery()
        )
        stmt = (
            select(
                _RUN.execution_id,
                _RUN.expected_entries,
                _RUN.persisted_events,
                func.coalesce(event_counts.c.cnt, 0),
            )
            .outerjoin(event_counts, event_counts.c.execution_id == _RUN.execution_id)
            .where(
                _RUN.source_type == WORKFLOW_SOURCE_TYPE,
                _RUN.occurred_at >= start,
                _RUN.occurred_at < end,
                _RUN.is_deleted == 0,
            )
        )
        rows = (await self.db.execute(stmt)).all()
        discrepancies = [
            {"execution_id": r[0], "expected": r[1], "persisted": r[2], "events": int(r[3])}
            for r in rows
            if r[1] != r[2] or int(r[3]) != r[2]
        ]
        return len(rows), discrepancies

    async def token_parity_mismatches(self, start: datetime, end: datetime) -> list[dict]:
        events = (
            select(
                _EVENT.execution_id,
                func.sum(_EVENT.input_tokens).label("i"),
                func.sum(_EVENT.output_tokens).label("o"),
                func.sum(_EVENT.total_tokens).label("t"),
            )
            .where(_EVENT.source == CHAT_SOURCE, _EVENT.is_deleted == 0)
            .group_by(_EVENT.execution_id)
            .subquery()
        )
        stmt = (
            select(
                _LOG.workflow_execution_id,
                _LOG.input_tokens,
                _LOG.output_tokens,
                _LOG.total_tokens,
                events.c.i,
                events.c.o,
                events.c.t,
            )
            .join(events, events.c.execution_id == _LOG.workflow_execution_id)
            .where(*_chat_logs(start, end))
        )
        mismatches = []
        for r in (await self.db.execute(stmt)).all():
            log_tokens = (r[1] or 0, r[2] or 0, r[3] or 0)
            event_tokens = (int(r[4] or 0), int(r[5] or 0), int(r[6] or 0))
            if log_tokens != event_tokens:
                mismatches.append({"execution_id": r[0], "log": list(log_tokens), "events": list(event_tokens)})
        return mismatches

    async def priced_events(self, start: datetime, end: datetime) -> list:
        """All priced events for the cost self-check, from any source"""
        stmt = select(
            _EVENT.execution_id,
            _EVENT.input_tokens,
            _EVENT.output_tokens,
            _EVENT.input_per_1k,
            _EVENT.output_per_1k,
            _EVENT.cost_usd,
        ).where(
            _EVENT.occurred_at >= start,
            _EVENT.occurred_at < end,
            _EVENT.input_per_1k.isnot(None),
            _EVENT.is_deleted == 0,
        )
        return (await self.db.execute(stmt)).all()

    async def unpriced_events(self, start: datetime, end: datetime) -> list[dict]:
        """Events the ledger could not price, placeholders for unreported usage included"""
        stmt = select(_EVENT.execution_id, _EVENT.call_index, _EVENT.provider_key, _EVENT.model_key).where(
            _EVENT.pricing_status == UNPRICED,
            _EVENT.occurred_at >= start,
            _EVENT.occurred_at < end,
            _EVENT.is_deleted == 0,
        )
        return [
            {"execution_id": r[0], "call_index": r[1], "provider": r[2], "model": r[3]}
            for r in (await self.db.execute(stmt)).all()
        ]

    async def joined_execution_count(self, start: datetime, end: datetime) -> int:
        """Chat logs correlated to a receipt"""
        stmt = (
            select(func.count())
            .select_from(_LOG)
            .join(
                _RUN,
                and_(_RUN.execution_id == _LOG.workflow_execution_id, _RUN.is_deleted == 0),
            )
            .where(*_chat_logs(start, end))
        )
        return int((await self.db.execute(stmt)).scalar() or 0)

    async def capture_run_count(self, start: datetime, end: datetime) -> int:
        """Count all capture receipts for the day (workflows and analyst runs)"""
        stmt = (
            select(func.count())
            .select_from(_RUN)
            .where(_RUN.occurred_at >= start, _RUN.occurred_at < end, _RUN.is_deleted == 0)
        )
        return int((await self.db.execute(stmt)).scalar() or 0)

    async def receipts_without_logs(self, start: datetime, end: datetime) -> list[tuple[str, str]]:
        """Returned chat receipts with no transcript log"""
        stmt = (
            select(_RUN.execution_id, _RUN.run_status)
            .outerjoin(
                _LOG,
                and_(_LOG.workflow_execution_id == _RUN.execution_id, _LOG.is_deleted == 0),
            )
            .where(
                _RUN.source == CHAT_SOURCE,
                _RUN.execution_outcome == RETURNED,
                _RUN.occurred_at >= start,
                _RUN.occurred_at < end,
                _RUN.is_deleted == 0,
                _LOG.id.is_(None),
            )
        )
        return [(row[0], row[1]) for row in (await self.db.execute(stmt)).all()]

    async def ledger_cost_by_status(self, start: datetime, end: datetime) -> dict[str, Decimal]:
        stmt = (
            select(_EVENT.pricing_status, func.coalesce(func.sum(_EVENT.cost_usd), 0))
            .where(
                _EVENT.source == CHAT_SOURCE,
                _EVENT.occurred_at >= start,
                _EVENT.occurred_at < end,
                _EVENT.is_deleted == 0,
            )
            .group_by(_EVENT.pricing_status)
        )
        return {row[0]: Decimal(row[1]) for row in (await self.db.execute(stmt)).all()}

    async def daily_stats_cost(self, day: date) -> Decimal:
        stmt = select(func.coalesce(func.sum(AgentExecutionDailyStatsModel.total_cost_usd), 0)).where(
            AgentExecutionDailyStatsModel.stat_date == day,
            AgentExecutionDailyStatsModel.is_deleted == 0,
        )
        return Decimal(str((await self.db.execute(stmt)).scalar() or 0))

    async def analyst_completeness(self, start: datetime, end: datetime) -> tuple[int, int]:
        receipts = (
            select(func.count())
            .select_from(_RUN)
            .where(
                _RUN.source_type == ANALYST_SOURCE_TYPE,
                _RUN.occurred_at >= start,
                _RUN.occurred_at < end,
                _RUN.is_deleted == 0,
            )
        )
        events = (
            select(func.count())
            .select_from(_EVENT)
            .where(
                _EVENT.source_type == ANALYST_SOURCE_TYPE,
                _EVENT.occurred_at >= start,
                _EVENT.occurred_at < end,
                _EVENT.is_deleted == 0,
            )
        )
        r = int((await self.db.execute(receipts)).scalar() or 0)
        e = int((await self.db.execute(events)).scalar() or 0)
        return r, e

    async def analyst_receipt_discrepancies(self, start: datetime, end: datetime) -> list[dict]:
        """Find analyst receipts that claim an entry but have no matching event row"""
        event_counts = (
            select(
                func.concat(_EVENT.execution_id, ":", cast(_EVENT.call_index, String)).label("receipt_id"),
                func.count().label("cnt"),
            )
            .where(_EVENT.source_type == ANALYST_SOURCE_TYPE, _EVENT.is_deleted == 0)
            .group_by("receipt_id")
            .subquery()
        )
        stmt = (
            select(
                _RUN.execution_id,
                _RUN.expected_entries,
                _RUN.persisted_events,
                func.coalesce(event_counts.c.cnt, 0),
            )
            .outerjoin(event_counts, event_counts.c.receipt_id == _RUN.execution_id)
            .where(
                _RUN.source_type == ANALYST_SOURCE_TYPE,
                _RUN.occurred_at >= start,
                _RUN.occurred_at < end,
                _RUN.is_deleted == 0,
            )
        )
        return [
            {"execution_id": r[0], "expected": r[1], "persisted": r[2], "events": int(r[3])}
            for r in (await self.db.execute(stmt)).all()
            if r[1] != r[2] or int(r[3]) != r[2]
        ]
