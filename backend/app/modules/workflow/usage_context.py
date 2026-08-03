"""Attribution context passed from every workflow entry point into the usage ledger"""

from dataclasses import dataclass
from typing import Optional
from uuid import UUID


@dataclass
class WorkflowUsageContext:
    """Attribution for a top-level workflow run's recorded usage"""

    source: str
    agent_id: Optional[UUID] = None
    workflow_id: Optional[UUID] = None
    conversation_id: Optional[UUID] = None
    source_type: str = "workflow"
    defer_capture: bool = False
