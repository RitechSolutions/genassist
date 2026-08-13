"""Unit tests for the Agent Performance exact-activity validation"""

from datetime import date, datetime, timezone

import pytest
from fastapi import HTTPException

from app.api.v1.routes.analytics import _validate_activity_bounds

FROM_DATE = date(2026, 8, 1)
TO_DATE = date(2026, 8, 7)
ACTIVITY_FROM = datetime(2026, 8, 1, tzinfo=timezone.utc)
ACTIVITY_TO = datetime(2026, 8, 8, tzinfo=timezone.utc)
NAIVE = datetime(2026, 8, 1)


def _expect_422(**kwargs):
    with pytest.raises(HTTPException) as excinfo:
        _validate_activity_bounds(**kwargs)
    assert excinfo.value.status_code == 422


def test_date_only_requests_pass_untouched():
    _validate_activity_bounds(FROM_DATE, TO_DATE, None, None)
    _validate_activity_bounds(None, None, None, None)


def test_date_only_comparison_stays_valid():
    _validate_activity_bounds(FROM_DATE, TO_DATE, None, None, compare=True)


def test_complete_aware_pair_with_a_full_date_range_passes():
    _validate_activity_bounds(FROM_DATE, TO_DATE, ACTIVITY_FROM, ACTIVITY_TO)


@pytest.mark.parametrize(
    "activity_from, activity_to",
    [
        pytest.param(ACTIVITY_FROM, None, id="start_only"),
        pytest.param(None, ACTIVITY_TO, id="end_only"),
    ],
)
def test_incomplete_activity_pairs_are_rejected(activity_from, activity_to):
    _expect_422(
        from_date=FROM_DATE,
        to_date=TO_DATE,
        activity_from_datetime=activity_from,
        activity_to_datetime=activity_to,
    )


@pytest.mark.parametrize(
    "activity_from, activity_to",
    [
        pytest.param(NAIVE, ACTIVITY_TO, id="naive_start"),
        pytest.param(ACTIVITY_FROM, NAIVE, id="naive_end"),
    ],
)
def test_naive_activity_bounds_are_rejected(activity_from, activity_to):
    _expect_422(
        from_date=FROM_DATE,
        to_date=TO_DATE,
        activity_from_datetime=activity_from,
        activity_to_datetime=activity_to,
    )


@pytest.mark.parametrize(
    "activity_from, activity_to",
    [
        pytest.param(ACTIVITY_TO, ACTIVITY_FROM, id="reversed"),
        pytest.param(ACTIVITY_FROM, ACTIVITY_FROM, id="zero_length"),
    ],
)
def test_non_increasing_activity_bounds_are_rejected(activity_from, activity_to):
    _expect_422(
        from_date=FROM_DATE,
        to_date=TO_DATE,
        activity_from_datetime=activity_from,
        activity_to_datetime=activity_to,
    )


@pytest.mark.parametrize(
    "from_date, to_date",
    [
        pytest.param(None, TO_DATE, id="missing_from_date"),
        pytest.param(FROM_DATE, None, id="missing_to_date"),
        pytest.param(None, None, id="missing_both"),
    ],
)
def test_exact_bounds_require_a_complete_bucket_date_range(from_date, to_date):
    _expect_422(
        from_date=from_date,
        to_date=to_date,
        activity_from_datetime=ACTIVITY_FROM,
        activity_to_datetime=ACTIVITY_TO,
    )


@pytest.mark.parametrize(
    "activity_from, activity_to",
    [
        pytest.param(ACTIVITY_FROM, ACTIVITY_TO, id="complete_pair"),
        pytest.param(ACTIVITY_FROM, None, id="start_only"),
        pytest.param(None, ACTIVITY_TO, id="end_only"),
    ],
)
def test_compare_with_any_activity_boundary_is_rejected(activity_from, activity_to):
    _expect_422(
        from_date=FROM_DATE,
        to_date=TO_DATE,
        activity_from_datetime=activity_from,
        activity_to_datetime=activity_to,
        compare=True,
    )
