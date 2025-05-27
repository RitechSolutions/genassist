from datetime import datetime, timezone


def convert_seconds_to_hhmmss(seconds: float) -> str:
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    seconds = int(seconds % 60)
    return f"{hours:02}:{minutes:02}:{seconds:02}"

def serialize_datetime(obj):
    """Convert datetime objects to ISO 8601 format."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError("Type not serializable")

def utc_now() -> datetime:
    """Timezone-aware replacement for datetime.utcnow()."""
    return datetime.now(timezone.utc)