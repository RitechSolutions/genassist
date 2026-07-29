"""Unit tests for the shared LLM usage query-param dependency"""

from datetime import date
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.schemas.llm_usage import BREAKDOWN_DIMENSIONS, LlmUsageQueryParams


def test_defaults_are_constructible_outside_a_request():
    params = LlmUsageQueryParams()
    assert params.from_date is None and params.to_date is None
    assert params.agent_id is None and params.group_id is None
    assert params.provider is None and params.model is None


def test_reversed_date_range_is_rejected():
    with pytest.raises(HTTPException) as exc:
        LlmUsageQueryParams(from_date=date(2026, 7, 8), to_date=date(2026, 7, 1))
    assert exc.value.status_code == 400


def test_single_day_range_is_allowed():
    params = LlmUsageQueryParams(from_date=date(2026, 7, 1), to_date=date(2026, 7, 1))
    assert params.from_date == params.to_date


def test_open_ended_ranges_are_allowed():
    assert LlmUsageQueryParams(from_date=date(2026, 7, 8)).to_date is None
    assert LlmUsageQueryParams(to_date=date(2026, 7, 1)).from_date is None


def test_filters_are_carried_through():
    agent_id, group_id = uuid4(), uuid4()
    params = LlmUsageQueryParams(agent_id=agent_id, group_id=group_id, provider="OpenAI", model="GPT-4o")
    assert params.agent_id == agent_id and params.group_id == group_id
    assert params.provider == "OpenAI" and params.model == "GPT-4o"


def test_breakdown_dimensions_match_the_literal():
    assert BREAKDOWN_DIMENSIONS == ("provider", "model", "agent", "source")
