import enum


class FileStatus(str, enum.Enum):
    UPLOADED = "uploaded"
    DELETED = "deleted"
    ERROR = "error"
    PROCESSED = "processed"


class JobStatus(str, enum.Enum):
    VALIDATING_FILES = "validating_files"
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"