"""Locks the LLM usage operation set on the bare app, without booting the lifespan"""

import pytest

from app import create_app

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
