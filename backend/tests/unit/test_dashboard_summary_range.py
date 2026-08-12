"""Unit tests for the /dashboard/summary range contract"""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

from app.api.v1.routes.dashboard import DEFAULT_SUMMARY_DAYS, resolve_summary_range

EXACT_FROM = datetime(2026, 8, 1, tzinfo=timezone.utc)
EXACT_TO = datetime(2026, 8, 8, tzinfo=timezone.utc)
OFFSET_FROM = datetime(2026, 8, 1, tzinfo=timezone(timedelta(hours=2)))
NAIVE_FROM = datetime(2026, 8, 1)
NAIVE_TO = datetime(2026, 8, 8)


def _rolling_days(resolved) -> float:
    return (resolved.to_date - resolved.from_date) / timedelta(days=1)


def test_no_range_arguments_fall_back_to_the_legacy_rolling_window():
    resolved = resolve_summary_range(None, None, None, False)
    assert _rolling_days(resolved) == DEFAULT_SUMMARY_DAYS
    assert resolved.exact is False
    assert resolved.from_date.utcoffset() is not None and resolved.to_date.utcoffset() is not None


def test_days_keeps_the_legacy_rolling_duration():
    resolved = resolve_summary_range(7, None, None, False)
    assert _rolling_days(resolved) == 7
    assert resolved.exact is False


def test_exact_pair_passes_through_unchanged():
    assert resolve_summary_range(None, EXACT_FROM, EXACT_TO, False) == (EXACT_FROM, EXACT_TO, True)


def test_exact_pair_keeps_a_non_utc_offset():
    assert resolve_summary_range(None, OFFSET_FROM, EXACT_TO, False) == (OFFSET_FROM, EXACT_TO, True)


def test_all_time_drops_both_bounds():
    assert resolve_summary_range(None, None, None, True) == (None, None, False)


def test_all_time_false_stays_inactive_beside_another_mode():
    assert resolve_summary_range(None, EXACT_FROM, EXACT_TO, False) == (EXACT_FROM, EXACT_TO, True)
    assert _rolling_days(resolve_summary_range(7, None, None, False)) == 7


@pytest.mark.parametrize(
    "days, from_datetime, to_datetime, all_time",
    [
        pytest.param(None, EXACT_FROM, None, False, id="start_only"),
        pytest.param(None, None, EXACT_TO, False, id="end_only"),
        pytest.param(None, NAIVE_FROM, EXACT_TO, False, id="naive_start"),
        pytest.param(None, EXACT_FROM, NAIVE_TO, False, id="naive_end"),
        pytest.param(None, EXACT_TO, EXACT_FROM, False, id="reversed"),
        pytest.param(None, EXACT_FROM, EXACT_FROM, False, id="zero_length"),
        pytest.param(7, EXACT_FROM, None, False, id="days_with_start"),
        pytest.param(7, None, EXACT_TO, False, id="days_with_end"),
        pytest.param(7, EXACT_FROM, EXACT_TO, False, id="days_with_exact_pair"),
        pytest.param(7, None, None, True, id="all_time_with_days"),
        pytest.param(None, EXACT_FROM, None, True, id="all_time_with_start"),
        pytest.param(None, None, EXACT_TO, True, id="all_time_with_end"),
        pytest.param(None, EXACT_FROM, EXACT_TO, True, id="all_time_with_exact_pair"),
    ],
)
def test_invalid_mode_combinations_are_rejected(days, from_datetime, to_datetime, all_time):
    with pytest.raises(HTTPException) as excinfo:
        resolve_summary_range(days, from_datetime, to_datetime, all_time)
    assert excinfo.value.status_code == 422
