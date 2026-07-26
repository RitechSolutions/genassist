import logging
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Optional

from injector import inject

from app.core.config.settings import settings
from app.core.utils.date_time_utils import utc_now
from app.repositories.llm_usage_control import LlmUsageControlRepository
from app.repositories.llm_usage_reconciliation import LlmUsageReconciliationRepository
from app.services.llm_usage_shadow_window import (
    GATE_VERSION,
    SHADOW_QUALIFYING_WINDOW_DAYS,
    evaluate_window,
    is_stale_verdict,
)

logger = logging.getLogger(__name__)

INTEGRITY_DISCREPANCY_BUDGET = 0.001
COST_EPSILON = Decimal("1e-9")
MAX_ENUMERATED = 50


@inject
class LlmUsageReconciliationService:
    """Evaluates the chat slice per UTC day"""

    def __init__(self, repo: LlmUsageReconciliationRepository, control_repo: LlmUsageControlRepository):
        self.repo = repo
        self.control_repo = control_repo

    async def reconcile(self) -> dict[str, Any]:
        control = await self.control_repo.get_singleton()
        if control is None or control.shadow_started_at is None:
            return {"status": "skipped", "reason": "shadow_not_started"}

        today = utc_now().date()
        shadow_start_day = control.shadow_started_at.astimezone(timezone.utc).date()
        last_complete = today - timedelta(days=1)
        # Bound the sweep so a long-running shadow never re-walks its whole history,
        # but never below the window the gate grades or those days could go unevaluated
        lookback_days = max(settings.LLM_USAGE_SHADOW_LOOKBACK_DAYS, SHADOW_QUALIFYING_WINDOW_DAYS)
        first_day = max(shadow_start_day, today - timedelta(days=lookback_days))

        existing = {r.report_date: r for r in await self.repo.reports_between(first_day, last_complete)}
        evaluated = []
        day = first_day
        while day <= last_complete:
            report = existing.get(day)
            # A day that passed under an older gate set is re-graded, not trusted
            if report is None or not report.passed or is_stale_verdict(report):
                data = await self._evaluate_day(day, control.capture_started_at)
                await self.repo.upsert_report(**data)
                evaluated.append({"date": day.isoformat(), "passed": data["passed"]})
            day += timedelta(days=1)

        # Monitoring outlives the pass; the stamp itself happens once
        shadow_passed = False
        if control.shadow_passed_at is None:
            shadow_passed = await self._maybe_stamp_shadow_passed(today)
        return {"status": "completed", "evaluated": evaluated, "shadow_passed": shadow_passed}

    async def _evaluate_day(self, day: date, capture_started_at: Optional[datetime] = None) -> dict[str, Any]:
        day_start = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
        end = day_start + timedelta(days=1)
        # On the activation day capture only owns the part of the day after it started;
        # everything before belongs to the backfill and cannot fail this report
        start = day_start
        if capture_started_at is not None:
            start = max(day_start, capture_started_at.astimezone(timezone.utc))

        logs_no_receipt = await self.repo.logs_without_receipts(start, end)
        total_receipts, integrity_disc = await self.repo.recorder_integrity(start, end)
        token_mismatches = await self.repo.token_parity_mismatches(start, end)
        cost_mismatches = self._cost_self_consistency(await self.repo.priced_events(start, end))
        unpriced = await self.repo.unpriced_events(start, end)
        joined = await self.repo.joined_execution_count(start, end)
        capture_runs = await self.repo.capture_run_count(start, end)
        receipts_no_log = await self.repo.receipts_without_logs(start, end)
        ledger_by_status = await self.repo.ledger_cost_by_status(start, end)
        daily_cost = await self.repo.daily_stats_cost(day)
        analyst_receipts, analyst_events = await self.repo.analyst_completeness(start, end)
        analyst_disc = await self.repo.analyst_receipt_discrepancies(start, end)

        integrity_rate = (len(integrity_disc) / total_receipts) if total_receipts else 0.0
        gate_logs = len(logs_no_receipt) == 0
        gate_integrity = integrity_rate < INTEGRITY_DISCREPANCY_BUDGET
        gate_tokens = len(token_mismatches) == 0
        gate_cost = len(cost_mismatches) == 0
        gate_unpriced = len(unpriced) == 0
        gate_analyst = len(analyst_disc) == 0
        passed = gate_logs and gate_integrity and gate_tokens and gate_cost and gate_unpriced and gate_analyst

        reasons = {
            "hard_gates": {
                "logs_without_receipts": {
                    "passed": gate_logs,
                    "count": len(logs_no_receipt),
                    "execution_ids": logs_no_receipt[:MAX_ENUMERATED],
                },
                "recorder_integrity": {
                    "passed": gate_integrity,
                    "rate": integrity_rate,
                    "discrepancies": integrity_disc[:MAX_ENUMERATED],
                },
                "token_parity": {"passed": gate_tokens, "mismatches": token_mismatches[:MAX_ENUMERATED]},
                "cost_self_consistency": {"passed": gate_cost, "mismatches": cost_mismatches[:MAX_ENUMERATED]},
                "unpriced_events": {
                    "passed": gate_unpriced,
                    "count": len(unpriced),
                    "events": unpriced[:MAX_ENUMERATED],
                },
                "analyst_completeness": {
                    "passed": gate_analyst,
                    "count": len(analyst_disc),
                    "discrepancies": analyst_disc[:MAX_ENUMERATED],
                },
            },
            "soft": {
                "receipts_without_logs": {
                    "count": len(receipts_no_log),
                    "by_run_status": dict(Counter(status for _, status in receipts_no_log)),
                    "execution_ids": [eid for eid, _ in receipts_no_log[:MAX_ENUMERATED]],
                },
                "ledger_cost_by_status": {k: str(v) for k, v in ledger_by_status.items()},
                "daily_stats_cost_usd": str(daily_cost),
                "analyst": {"receipts": analyst_receipts, "events": analyst_events},
            },
        }
        metrics = {
            "gate_version": GATE_VERSION,
            "capture_runs": capture_runs,
            "joined_executions": joined,
            "total_receipts": total_receipts,
            "logs_without_receipts": len(logs_no_receipt),
            "receipts_without_logs": len(receipts_no_log),
            "integrity_discrepancies": len(integrity_disc),
            "token_mismatches": len(token_mismatches),
            "cost_mismatches": len(cost_mismatches),
            "unpriced_events": len(unpriced),
            "analyst_discrepancies": len(analyst_disc),
            "ledger_cost_usd": str(sum(ledger_by_status.values(), Decimal(0))),
            "daily_stats_cost_usd": str(daily_cost),
        }
        return {
            "report_date": day,
            "interval_start": start,
            "interval_end": end,
            "passed": passed,
            "reasons": reasons,
            "metrics": metrics,
        }

    @staticmethod
    def _cost_self_consistency(priced_rows: list) -> list[dict]:
        """Recompute each priced event from its snapshot rates"""
        thousand = Decimal(1000)
        mismatches = []
        for execution_id, in_tok, out_tok, in_rate, out_rate, stored in priced_rows:
            expected = (Decimal(int(in_tok)) / thousand) * Decimal(in_rate) + (
                Decimal(int(out_tok)) / thousand
            ) * Decimal(out_rate)
            if stored is None or abs(Decimal(stored) - expected) > COST_EPSILON:
                mismatches.append({"execution_id": execution_id, "stored": str(stored), "expected": str(expected)})
        return mismatches

    async def _maybe_stamp_shadow_passed(self, today: date) -> bool:
        window = await evaluate_window(self.repo, today)
        if not window.passed:
            logger.info("Shadow window not qualifying; not stamping (%s)", window.describe())
            return False

        await self.control_repo.mark_shadow_passed()
        logger.info(
            "Shadow reconciliation passed: %s capture runs over %s days", window.capture_runs, len(window.required)
        )
        return True
