"""Unit tests for the UTC daily-stat bucket conversions"""

from datetime import date, datetime, timedelta, timezone

from app.core.utils.date_time_utils import exact_interval_bucket_dates, rolling_window_bucket_dates

TZ_PLUS_2 = timezone(timedelta(hours=2))
TZ_MINUS_7 = timezone(timedelta(hours=-7))


def test_exact_interval_covers_every_touched_utc_day():
    assert exact_interval_bucket_dates(
        datetime(2026, 8, 1, 15, 0, tzinfo=timezone.utc),
        datetime(2026, 8, 8, tzinfo=timezone.utc),
    ) == (date(2026, 8, 1), date(2026, 8, 7))


def test_exact_interval_of_one_day_is_a_single_bucket():
    start = datetime(2026, 8, 1, tzinfo=timezone.utc)
    assert exact_interval_bucket_dates(start, start + timedelta(days=1)) == (
        date(2026, 8, 1),
        date(2026, 8, 1),
    )


def test_exact_interval_converts_local_offsets_to_utc_days():
    assert exact_interval_bucket_dates(
        datetime(2026, 8, 2, tzinfo=TZ_PLUS_2),
        datetime(2026, 8, 3, tzinfo=TZ_PLUS_2),
    ) == (date(2026, 8, 1), date(2026, 8, 2))

    assert exact_interval_bucket_dates(
        datetime(2026, 8, 2, tzinfo=TZ_MINUS_7),
        datetime(2026, 8, 3, tzinfo=TZ_MINUS_7),
    ) == (date(2026, 8, 2), date(2026, 8, 3))


def test_rolling_window_keeps_whole_utc_days():
    assert rolling_window_bucket_dates(
        datetime(2026, 1, 1, tzinfo=timezone.utc),
        datetime(2026, 1, 31, tzinfo=timezone.utc),
    ) == (date(2026, 1, 1), date(2026, 1, 31))


def test_rolling_window_rounds_a_mid_day_start_up():
    assert rolling_window_bucket_dates(
        datetime(2026, 1, 1, 13, 30, tzinfo=timezone.utc),
        datetime(2026, 1, 31, 13, 30, tzinfo=timezone.utc),
    ) == (date(2026, 1, 2), date(2026, 1, 31))
