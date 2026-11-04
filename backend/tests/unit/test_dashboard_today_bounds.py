from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

from app.api.v1.routes.dashboard import resolve_today_bounds

VANCOUVER = timezone(timedelta(hours=-7))
TODAY_START = datetime(2026, 10, 30, tzinfo=VANCOUVER)
TODAY_END = datetime(2026, 10, 31, tzinfo=VANCOUVER)
NAIVE_START = datetime(2026, 10, 30)
NAIVE_END = datetime(2026, 10, 31)


def test_no_bounds_keep_the_server_day():
    assert resolve_today_bounds(None, None) is None


def test_aware_pair_passes_through_unchanged():
    assert resolve_today_bounds(TODAY_START, TODAY_END) == (TODAY_START, TODAY_END)


@pytest.mark.parametrize(
    "today_start, today_end",
    [
        pytest.param(TODAY_START, None, id="start_only"),
        pytest.param(None, TODAY_END, id="end_only"),
        pytest.param(NAIVE_START, TODAY_END, id="naive_start"),
        pytest.param(TODAY_START, NAIVE_END, id="naive_end"),
        pytest.param(TODAY_END, TODAY_START, id="reversed"),
        pytest.param(TODAY_START, TODAY_START, id="zero_length"),
    ],
)
def test_invalid_bounds_are_rejected(today_start, today_end):
    with pytest.raises(HTTPException) as excinfo:
        resolve_today_bounds(today_start, today_end)
    assert excinfo.value.status_code == 422
