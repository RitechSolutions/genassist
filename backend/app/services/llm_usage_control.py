import logging

from injector import inject

from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.db.models.llm_usage import LlmUsageControlModel
from app.repositories.llm_usage_control import LlmUsageControlRepository
from app.repositories.llm_usage_reconciliation import LlmUsageReconciliationRepository
from app.schemas.llm_usage_control import (
    COST_SOURCE_DAILY_STATS,
    COST_SOURCE_LEDGER,
    LlmUsageControlRead,
)

logger = logging.getLogger(__name__)

# Shadow mode must stay healthy for this many days in a row before cutover can turn on
SHADOW_QUALIFYING_WINDOW_DAYS = 7


@inject
class LlmUsageControlService:
    """Control plane for the LLM usage ledger: capture activation, shadow start, and
    the dashboard cutover switch. Capture is one-way; only cutover is reversible"""

    def __init__(
        self,
        repo: LlmUsageControlRepository,
        reconciliation_repo: LlmUsageReconciliationRepository,
    ):
        self.repo = repo
        self.reconciliation_repo = reconciliation_repo

    async def get_control(self) -> LlmUsageControlRead:
        control = await self._require_singleton()
        return self._to_read(control)

    async def activate_capture(self) -> LlmUsageControlRead:
        """Enable capture and stamp the backfill boundary"""
        control = await self._require_singleton()
        if not control.capture_enabled:
            control = await self.repo.activate_capture()
        return self._to_read(control)

    async def start_shadow(self) -> LlmUsageControlRead:
        control = await self._require_singleton()
        if not control.capture_enabled:
            raise AppException(error_key=ErrorKey.LLM_USAGE_CAPTURE_NOT_ENABLED, status_code=409)
        if control.shadow_passed_at is not None:
            raise AppException(error_key=ErrorKey.LLM_USAGE_SHADOW_ALREADY_PASSED, status_code=409)
        if control.shadow_started_at is not None:
            raise AppException(error_key=ErrorKey.LLM_USAGE_SHADOW_ALREADY_RUNNING, status_code=409)
        control = await self.repo.start_shadow()
        return self._to_read(control)

    async def set_cutover(self, enabled: bool) -> LlmUsageControlRead:
        control = await self._require_singleton()
        if enabled:
            await self._guard_cutover_enable(control)
        control = await self.repo.set_cutover(enabled)
        return self._to_read(control)

    async def _guard_cutover_enable(self, control: LlmUsageControlModel) -> None:
        """Cutover may flip on only with capture active, shadow passed, and the passing
        window still green"""
        if not control.capture_enabled:
            raise AppException(error_key=ErrorKey.LLM_USAGE_CAPTURE_NOT_ENABLED, status_code=409)
        if control.shadow_passed_at is None:
            raise AppException(error_key=ErrorKey.LLM_USAGE_SHADOW_NOT_PASSED, status_code=409)

        reports = await self.reconciliation_repo.recent_reports(SHADOW_QUALIFYING_WINDOW_DAYS)
        window_current = len(reports) >= SHADOW_QUALIFYING_WINDOW_DAYS and all(r.passed for r in reports)
        if not window_current:
            failing = [r.report_date.isoformat() for r in reports if not r.passed]
            detail = f"Qualifying window broken; failing days: {failing}" if failing else "Qualifying window incomplete"
            raise AppException(
                error_key=ErrorKey.LLM_USAGE_SHADOW_WINDOW_STALE,
                status_code=409,
                error_detail=detail,
            )

    async def _require_singleton(self) -> LlmUsageControlModel:
        control = await self.repo.get_singleton()
        if control is None:
            raise AppException(error_key=ErrorKey.LLM_USAGE_CONTROL_NOT_FOUND, status_code=404)
        return control

    @staticmethod
    def _to_read(control: LlmUsageControlModel) -> LlmUsageControlRead:
        cost_source = COST_SOURCE_LEDGER if control.ledger_cutover_enabled else COST_SOURCE_DAILY_STATS
        return LlmUsageControlRead(
            capture_enabled=control.capture_enabled,
            capture_started_at=control.capture_started_at,
            shadow_started_at=control.shadow_started_at,
            shadow_passed_at=control.shadow_passed_at,
            ledger_cutover_enabled=control.ledger_cutover_enabled,
            cost_source=cost_source,
        )
