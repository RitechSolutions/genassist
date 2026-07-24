"""Integration tests for shadow reconciliation and the cutover gate"""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config.settings import settings
from app.core.exceptions.exception_classes import AppException
from app.core.utils.enums.conversation_status_enum import ConversationStatus
from app.core.utils.enums.conversation_type_enum import ConversationType
from app.db.models.agent_response_log import AgentResponseLogModel
from app.db.models.conversation import ConversationModel
from app.db.models.llm_usage import (
    CONTROL_SINGLETON_KEY,
    LlmUsageCaptureRunModel,
    LlmUsageEventModel,
)
from app.db.models.message_model import TranscriptMessageModel
from app.db.seed.seed_data_config import seed_test_data
from app.repositories.llm_usage_control import LlmUsageControlRepository
from app.repositories.llm_usage_reconciliation import LlmUsageReconciliationRepository
from app.services.llm_usage_control import LlmUsageControlService
from app.services.llm_usage_reconciliation import LlmUsageReconciliationService

DAY = date(2024, 3, 15)


def _at(day: date, hour: int, minute: int = 0, second: int = 0) -> datetime:
    return datetime(day.year, day.month, day.day, hour, minute, second, tzinfo=timezone.utc)


@pytest_asyncio.fixture
async def db(app_def):
    engine = create_async_engine(settings.DATABASE_URL)
    maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as session:
        try:
            yield session
        finally:
            await session.rollback()
    await engine.dispose()


class Seeder:

    def __init__(self, db: AsyncSession):
        self.db = db
        self.prefix = f"recon-{uuid4().hex[:12]}-"
        self.conv_id = None
        self.report_dates: list[date] = []

    async def _conversation(self):
        if self.conv_id is None:
            conv = ConversationModel(
                id=uuid4(),
                operator_id=seed_test_data.operator_id,
                data_source_id=seed_test_data.data_source_id,
                status=ConversationStatus.FINALIZED.value,
                conversation_type=ConversationType.PROGRESSIVE.value,
                transcription="[]",
            )
            self.db.add(conv)
            await self.db.commit()
            self.conv_id = conv.id
        return self.conv_id

    def new_execution_id(self) -> str:
        return f"{self.prefix}{uuid4().hex[:8]}"

    async def add_log(self, execution_id, logged_at, tokens):
        conv_id = await self._conversation()
        msg = TranscriptMessageModel(
            id=uuid4(),
            conversation_id=conv_id,
            start_time=0.0,
            end_time=1.0,
            speaker="agent",
            text="x",
            type="message",
            sequence_number=1,
        )
        self.db.add(msg)
        await self.db.commit()
        self.db.add(
            AgentResponseLogModel(
                id=uuid4(),
                conversation_id=conv_id,
                transcript_message_id=msg.id,
                raw_response="{}",
                workflow_execution_id=execution_id,
                input_tokens=tokens[0],
                output_tokens=tokens[1],
                total_tokens=tokens[2],
                logged_at=logged_at,
            )
        )
        await self.db.commit()

    async def add_receipt(
        self, execution_id, occurred_at, *, expected, persisted, run_status="completed", outcome="returned"
    ):
        self.db.add(
            LlmUsageCaptureRunModel(
                id=uuid4(),
                execution_id=execution_id,
                source_type="workflow",
                source="chat",
                execution_outcome=outcome,
                run_status=run_status,
                expected_entries=expected,
                persisted_events=persisted,
                occurred_at=occurred_at,
            )
        )
        await self.db.commit()

    async def add_event(
        self,
        execution_id,
        call_index,
        occurred_at,
        tokens,
        *,
        in_rate=None,
        out_rate=None,
        cost=None,
        status="unpriced",
    ):
        self.db.add(
            LlmUsageEventModel(
                id=uuid4(),
                execution_id=execution_id,
                call_index=call_index,
                source_type="workflow",
                source="chat",
                input_tokens=tokens[0],
                output_tokens=tokens[1],
                total_tokens=tokens[2],
                input_per_1k=in_rate,
                output_per_1k=out_rate,
                cost_usd=cost,
                pricing_status=status,
                occurred_at=occurred_at,
            )
        )
        await self.db.commit()

    async def set_report(self, report_date, passed, joined):
        repo = LlmUsageReconciliationRepository(self.db)
        await repo.upsert_report(
            report_date=report_date,
            interval_start=_at(report_date, 0),
            interval_end=_at(report_date, 0) + timedelta(days=1),
            passed=passed,
            reasons={},
            metrics={"joined_executions": joined},
        )
        self.report_dates.append(report_date)

    async def start_shadow(self, started_at):
        await self.db.execute(
            text(
                "UPDATE llm_usage_control SET capture_enabled=true, capture_started_at=:c, "
                "shadow_started_at=:s WHERE singleton_key=:k"
            ),
            {"c": started_at, "s": started_at, "k": CONTROL_SINGLETON_KEY},
        )
        await self.db.commit()

    async def cleanup(self):
        like = self.prefix + "%"
        await self.db.execute(text("DELETE FROM llm_usage_events WHERE execution_id LIKE :p"), {"p": like})
        await self.db.execute(text("DELETE FROM llm_usage_capture_runs WHERE execution_id LIKE :p"), {"p": like})
        if self.conv_id is not None:
            # conversation CASCADE clears its transcript messages and response logs
            await self.db.execute(text("DELETE FROM conversations WHERE id = :i"), {"i": self.conv_id})
        for d in set(self.report_dates):
            await self.db.execute(text("DELETE FROM llm_usage_reconciliation_reports WHERE report_date = :d"), {"d": d})
        await self.db.execute(
            text(
                "UPDATE llm_usage_control SET capture_enabled=false, capture_started_at=NULL, "
                "shadow_started_at=NULL, shadow_passed_at=NULL, ledger_cutover_enabled=false "
                "WHERE singleton_key=:k"
            ),
            {"k": CONTROL_SINGLETON_KEY},
        )
        await self.db.commit()


@pytest_asyncio.fixture
async def seeder(db):
    s = Seeder(db)
    try:
        yield s
    finally:
        await s.cleanup()


def _service(db) -> LlmUsageReconciliationService:
    return LlmUsageReconciliationService(LlmUsageReconciliationRepository(db), LlmUsageControlRepository(db))



@pytest.mark.asyncio
async def test_matched_execution_day_passes(seeder, db):
    exec_id = seeder.new_execution_id()
    await seeder.add_log(exec_id, _at(DAY, 10), tokens=(10, 5, 15))
    await seeder.add_receipt(exec_id, _at(DAY, 10), expected=1, persisted=1)
    await seeder.add_event(exec_id, 0, _at(DAY, 10), tokens=(10, 5, 15))

    report = await _service(db)._evaluate_day(DAY)
    assert report["passed"] is True
    assert report["metrics"]["joined_executions"] == 1
    assert report["metrics"]["logs_without_receipts"] == 0


@pytest.mark.asyncio
async def test_midnight_boundary_is_immune(seeder, db):
    exec_id = seeder.new_execution_id()
    await seeder.add_log(exec_id, _at(DAY, 23, 59, 30), tokens=(10, 5, 15))
    await seeder.add_receipt(exec_id, _at(DAY + timedelta(days=1), 0, 0, 30), expected=1, persisted=1)
    await seeder.add_event(exec_id, 0, _at(DAY + timedelta(days=1), 0, 0, 30), tokens=(10, 5, 15))

    report = await _service(db)._evaluate_day(DAY)
    assert report["passed"] is True
    assert report["metrics"]["joined_executions"] == 1


@pytest.mark.asyncio
async def test_log_without_receipt_fails(seeder, db):
    exec_id = seeder.new_execution_id()
    await seeder.add_log(exec_id, _at(DAY, 10), tokens=(10, 5, 15))

    report = await _service(db)._evaluate_day(DAY)
    assert report["passed"] is False
    assert report["metrics"]["logs_without_receipts"] == 1


@pytest.mark.asyncio
async def test_token_parity_mismatch_fails(seeder, db):
    exec_id = seeder.new_execution_id()
    await seeder.add_log(exec_id, _at(DAY, 10), tokens=(10, 5, 15))
    await seeder.add_receipt(exec_id, _at(DAY, 10), expected=1, persisted=1)
    await seeder.add_event(exec_id, 0, _at(DAY, 10), tokens=(10, 5, 20))  # total 20 != log 15

    report = await _service(db)._evaluate_day(DAY)
    assert report["passed"] is False
    assert report["metrics"]["token_mismatches"] == 1


@pytest.mark.asyncio
async def test_recorder_integrity_discrepancy_fails(seeder, db):
    exec_id = seeder.new_execution_id()
    # receipt claims 2 expected but only 1 persisted / 1 event exists
    await seeder.add_receipt(exec_id, _at(DAY, 10), expected=2, persisted=1)
    await seeder.add_event(exec_id, 0, _at(DAY, 10), tokens=(1, 1, 2))

    report = await _service(db)._evaluate_day(DAY)
    assert report["passed"] is False
    assert report["metrics"]["integrity_discrepancies"] == 1


@pytest.mark.asyncio
async def test_cost_self_consistency_flags_corruption(seeder, db):
    exec_id = seeder.new_execution_id()
    await seeder.add_receipt(exec_id, _at(DAY, 10), expected=1, persisted=1)
    # priced event whose stored cost does not match rate * tokens
    await seeder.add_event(
        exec_id,
        0,
        _at(DAY, 10),
        tokens=(1000, 1000, 2000),
        in_rate=Decimal("0.001"),
        out_rate=Decimal("0.002"),
        cost=Decimal("9.9"),
        status="fallback",
    )
    report = await _service(db)._evaluate_day(DAY)
    assert report["passed"] is False
    assert report["metrics"]["cost_mismatches"] == 1


@pytest.mark.asyncio
async def test_receipt_without_log_is_soft_and_classified(seeder, db):
    returned = seeder.new_execution_id()
    await seeder.add_receipt(returned, _at(DAY, 12), expected=0, persisted=0, run_status="paused")
    raised = seeder.new_execution_id()
    await seeder.add_receipt(raised, _at(DAY, 13), expected=0, persisted=0, run_status="failed", outcome="raised")

    report = await _service(db)._evaluate_day(DAY)
    assert report["passed"] is True
    soft = report["reasons"]["soft"]["receipts_without_logs"]
    assert soft["count"] == 1  # only the returned one
    assert soft["by_run_status"] == {"paused": 1}



@pytest.mark.asyncio
async def test_shadow_passes_with_streak_and_volume(seeder, db):
    today = date(2024, 6, 10)
    await seeder.start_shadow(_at(today - timedelta(days=10), 0))
    for i in range(7):
        await seeder.set_report(today - timedelta(days=7 - i), passed=True, joined=3)

    passed = await _service(db)._maybe_stamp_shadow_passed(today)
    assert passed is True
    control = await LlmUsageControlRepository(db).get_singleton()
    assert control.shadow_passed_at is not None


@pytest.mark.asyncio
async def test_no_stamp_when_streak_incomplete(seeder, db):
    today = date(2024, 6, 10)
    for i in range(6):  # only 6 of the required 7 days present
        await seeder.set_report(today - timedelta(days=7 - i), passed=True, joined=3)
    assert await _service(db)._maybe_stamp_shadow_passed(today) is False


@pytest.mark.asyncio
async def test_failed_day_resets_streak(seeder, db):
    today = date(2024, 6, 10)
    for i in range(7):
        await seeder.set_report(today - timedelta(days=7 - i), passed=(i != 3), joined=3)
    assert await _service(db)._maybe_stamp_shadow_passed(today) is False


@pytest.mark.asyncio
async def test_empty_week_never_passes(seeder, db):
    today = date(2024, 6, 10)
    for i in range(7):
        await seeder.set_report(today - timedelta(days=7 - i), passed=True, joined=0)
    assert await _service(db)._maybe_stamp_shadow_passed(today) is False


@pytest.mark.asyncio
async def test_rerun_repairs_a_failed_report(seeder, db):
    repo = LlmUsageReconciliationRepository(db)
    seeder.report_dates.append(DAY)
    await seeder.set_report(DAY, passed=False, joined=0)
    await repo.upsert_report(
        report_date=DAY,
        interval_start=_at(DAY, 0),
        interval_end=_at(DAY, 0) + timedelta(days=1),
        passed=True,
        reasons={},
        metrics={"joined_executions": 5},
    )
    reports = await repo.reports_between(DAY, DAY)
    assert len(reports) == 1 and reports[0].passed is True


def _control_service(db) -> LlmUsageControlService:
    return LlmUsageControlService(LlmUsageControlRepository(db), LlmUsageReconciliationRepository(db))


@pytest.mark.asyncio
async def test_cutover_409_before_shadow_passed(seeder, db):
    await seeder.start_shadow(_at(DAY, 0))
    with pytest.raises(AppException) as exc:
        await _control_service(db).set_cutover(True)
    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_cutover_enable_succeeds_when_window_current(seeder, db):
    today = date(2024, 6, 10)
    await seeder.start_shadow(_at(today - timedelta(days=10), 0))
    for i in range(7):
        await seeder.set_report(today - timedelta(days=7 - i), passed=True, joined=3)
    await LlmUsageControlRepository(db).mark_shadow_passed()

    result = await _control_service(db).set_cutover(True)
    assert result.ledger_cutover_enabled is True
    assert result.cost_source == "llm_usage_ledger"


@pytest.mark.asyncio
async def test_cutover_disable_always_allowed(seeder, db):
    result = await _control_service(db).set_cutover(False)
    assert result.ledger_cutover_enabled is False
