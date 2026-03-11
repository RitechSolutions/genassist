from datetime import date, datetime, timedelta, timezone

from dateutil.relativedelta import relativedelta


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

def shift_datetime(unit: str, amount: int, operation: str = 'add', base_time: datetime = None) -> datetime:
    """
    Shift the given datetime by a specified amount of time units.

    Args:
        unit (str): One of 'years', 'months', 'days', 'hours', 'minutes', 'seconds', etc.
        amount (int): Number of units to shift.
        operation (str): 'add' or 'subtract'. Defaults to 'add'.
        base_time (datetime): Starting point. Defaults to datetime.now(timezone.utc).

    Returns:
        datetime: The resulting shifted datetime.
    """
    if base_time is None:
        base_time = datetime.now(timezone.utc)

    if operation == 'subtract':
        amount = -amount
    elif operation != 'add':
        raise ValueError("operation must be either 'add' or 'subtract'")

    kwargs = {unit: amount}
    return base_time + relativedelta(**kwargs)


def previous_period(from_date: date, to_date: date) -> tuple[date, date]:
    """Return the equivalent previous period for comparison.

    Given a date range [from_date, to_date], returns [prev_from, prev_to]
    where prev_to is the day before from_date and prev_from is the same
    number of days back.
    """
    duration = (to_date - from_date).days
    prev_to = from_date - timedelta(days=1)
    prev_from = prev_to - timedelta(days=duration)
    return prev_from, prev_to