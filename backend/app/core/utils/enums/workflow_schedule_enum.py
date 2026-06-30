import enum


class WorkflowScheduleRunStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ThreadIdMode(str, enum.Enum):
    PER_RUN = "per_run"
    FIXED = "fixed"