from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

# Which system the dashboard reads cost from. Flips to the ledger only at cutover
COST_SOURCE_DAILY_STATS = "daily_stats"
COST_SOURCE_LEDGER = "llm_usage_ledger"


class LlmUsageControlRead(BaseModel):
    """Capture / shadow / cutover state of the LLM usage ledger, plus the active cost source"""

    model_config = ConfigDict(from_attributes=True)

    capture_enabled: bool
    capture_started_at: Optional[datetime] = None
    shadow_started_at: Optional[datetime] = None
    shadow_passed_at: Optional[datetime] = None
    ledger_cutover_enabled: bool
    cost_source: str


class LlmUsageCutoverRequest(BaseModel):
    """Toggle the dashboard cost source between healed daily stats and the ledger"""

    enabled: bool
