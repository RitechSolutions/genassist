"""Locks the LLM usage operation set on the bare app, without booting the lifespan"""

from uuid import uuid4

import pytest
from fastapi import HTTPException

from app import create_app
from app.api.v1.routes.llm_usage import get_breakdown
from app.schemas.llm_usage import BREAKDOWN_DIMENSIONS, EXPORT_DIMENSIONS, LlmUsageQueryParams

PREFIX = "/api/analytics/llm-usage"

EXPECTED_OPERATIONS = {
    ("GET", f"{PREFIX}/control"),
    ("POST", f"{PREFIX}/capture"),
    ("POST", f"{PREFIX}/backfill"),
    ("GET", f"{PREFIX}/summary"),
    ("GET", f"{PREFIX}/timeseries"),
    ("GET", f"{PREFIX}/breakdown"),
    ("GET", f"{PREFIX}/filter-options"),
    ("GET", f"{PREFIX}/export"),
}


@pytest.fixture(scope="module")
def app():
    return create_app()


def test_route_table_exposes_exactly_the_expected_operations(app):
    operations = {
        (method, route.path)
        for route in app.routes
        for method in getattr(route, "methods", None) or ()
        if getattr(route, "path", "").startswith(PREFIX)
        if method not in {"HEAD", "OPTIONS"}
    }
    assert operations == EXPECTED_OPERATIONS


def test_openapi_exposes_exactly_the_expected_operations(app):
    paths = app.openapi()["paths"]
    operations = {
        (method.upper(), path) for path, methods in paths.items() if path.startswith(PREFIX) for method in methods
    }
    assert operations == EXPECTED_OPERATIONS


def _dimension_enum(app, path: str) -> list[str]:
    params = app.openapi()["paths"][path]["get"]["parameters"]
    return next(p["schema"]["enum"] for p in params if p["name"] == "dimension")


def test_breakdown_documents_every_dimension(app):
    assert _dimension_enum(app, f"{PREFIX}/breakdown") == list(BREAKDOWN_DIMENSIONS)


def test_export_rejects_the_drill_down_dimensions(app):
    enum = _dimension_enum(app, f"{PREFIX}/export")
    assert enum == list(EXPORT_DIMENSIONS)
    assert "llm" not in enum and "evaluation_method" not in enum
    assert "node" not in enum


def test_breakdown_summary_covers_the_widened_dimension_set(app):
    summary = app.openapi()["paths"][f"{PREFIX}/breakdown"]["get"]["summary"]
    assert "LLM" in summary and "evaluation method" in summary
    assert "node" in summary


class FakeBreakdownService:
    def __init__(self):
        self.calls = []

    async def get_breakdown(self, params, dimension):
        self.calls.append(dimension)
        return None


@pytest.mark.asyncio
@pytest.mark.parametrize("params", [LlmUsageQueryParams(), LlmUsageQueryParams(group_id=uuid4())])
async def test_breakdown_route_requires_an_agent_for_the_node_dimension(params):
    service = FakeBreakdownService()
    with pytest.raises(HTTPException) as exc:
        await get_breakdown(params=params, dimension="node", service=service)
    assert exc.value.status_code == 400
    assert service.calls == []


@pytest.mark.asyncio
async def test_breakdown_route_serves_the_node_dimension_for_a_single_agent():
    service = FakeBreakdownService()
    await get_breakdown(params=LlmUsageQueryParams(agent_id=uuid4()), dimension="node", service=service)
    assert service.calls == ["node"]


@pytest.mark.asyncio
async def test_breakdown_route_leaves_other_dimensions_unscoped():
    service = FakeBreakdownService()
    await get_breakdown(params=LlmUsageQueryParams(), dimension="provider", service=service)
    assert service.calls == ["provider"]
