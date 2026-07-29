import logging

from injector import inject

from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.db.models.llm_usage import LlmUsageControlModel
from app.repositories.llm_usage_control import LlmUsageControlRepository
from app.schemas.llm_usage_control import LlmUsageControlRead

logger = logging.getLogger(__name__)


@inject
class LlmUsageControlService:
    """Capture activation control plane for the LLM usage ledger. Capture is one-way"""

    def __init__(self, repo: LlmUsageControlRepository):
        self.repo = repo

    async def get_control(self) -> LlmUsageControlRead:
        control = await self._require_singleton()
        return self._to_read(control)

    async def activate_capture(self) -> LlmUsageControlRead:
        """Enable capture and stamp the backfill boundary.

        Capture ships on, so this is normally a no-op; it still repairs a row that is
        enabled without a stamp, which would otherwise leave the backfill with no cut-off.
        """
        control = await self._require_singleton()
        if not control.capture_enabled or control.capture_started_at is None:
            control = await self.repo.activate_capture()
        return self._to_read(control)

    async def _require_singleton(self) -> LlmUsageControlModel:
        control = await self.repo.get_singleton()
        if control is None:
            raise AppException(error_key=ErrorKey.LLM_USAGE_CONTROL_NOT_FOUND, status_code=404)
        return control

    @staticmethod
    def _to_read(control: LlmUsageControlModel) -> LlmUsageControlRead:
        return LlmUsageControlRead(
            capture_enabled=control.capture_enabled,
            capture_started_at=control.capture_started_at,
        )
