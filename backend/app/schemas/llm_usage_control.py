from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class LlmUsageControlRead(BaseModel):
    """Capture state of the LLM usage ledger"""

    model_config = ConfigDict(from_attributes=True)

    capture_enabled: bool
    capture_started_at: Optional[datetime] = None
