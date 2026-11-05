"""Prompt editor Check and Optimize run in their own scope behind a kept-alive response"""

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder
from fastapi.testclient import TestClient

import app.api.v1.routes.prompt_editor as route
import app.core.keepalive_json_response as keepalive
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.core.exceptions.exception_handler import init_error_handlers
from app.middlewares.read_after_write_middleware import ReadAfterWriteMiddleware
from app.schemas.prompt_editor import (
    PromptEvalResponse,
    PromptEvalSummary,
    PromptOptimizeResponse,
    PromptRunProvenance,
)

WORKFLOW_ID = UUID("0199e3a0-0000-7000-8000-000000000004")
PROVIDER_ID = UUID("0199e3a0-0000-7000-8000-000000000005")
CASE_ID = UUID("0199e3a0-0000-7000-8000-000000000006")
NOW = datetime(2026, 11, 5, 12, 0, tzinfo=timezone.utc)
CONTEXT = f"{WORKFLOW_ID}/node-1/system_prompt"
EVALUATE_BODY = {"prompt_content": "p", "provider_id": str(PROVIDER_ID), "techniques": ["exact_match"]}
OPTIMIZE_BODY = {"provider_id": str(PROVIDER_ID), "current_prompt": "p"}

EVALUATION = PromptEvalResponse(
    results=[],
    summary=PromptEvalSummary(
        total=0, passed=0, failed=0, inconclusive=0, execution_failed=0, scoring_failed=0, skipped=0, scored=0
    ),
    provenance=PromptRunProvenance(
        provider_id=PROVIDER_ID,
        provider_key="",
        model="m",
        techniques=["exact_match"],
        evaluated_case_ids=[CASE_ID],
        total_cases=1,
        ran_at=NOW,
        latency_ms_total=1,
        usage_total={},
        budget_seconds=70,
    ),
)


@pytest.fixture
def editor(monkeypatch):
    state = SimpleNamespace(calls=[], fail=None)

    class FakeService:
        async def evaluate_prompt(self, *args):
            state.calls.append("evaluate")
            return EVALUATION

        async def optimize_prompt(self, *args):
            state.calls.append("optimize")
            raise state.fail

    def resolve(cls):
        state.calls.append("resolve")
        return FakeService()

    @asynccontextmanager
    async def scope():
        state.calls.append("scope-enter")
        yield
        state.calls.append("scope-exit")

    async def remember(request):
        pass

    monkeypatch.setattr(route, "injector", SimpleNamespace(get=resolve))
    monkeypatch.setattr(keepalive, "create_tenant_request_scope", scope)
    monkeypatch.setattr(ReadAfterWriteMiddleware, "remember_write", remember)
    monkeypatch.delenv("ENV", raising=False)

    app = FastAPI()
    init_error_handlers(app)
    app.add_api_route(
        "/evaluate/{workflow_id}/{node_id}/{prompt_field}",
        route.evaluate_prompt,
        methods=["POST"],
        response_model=PromptEvalResponse,
    )
    app.add_api_route(
        "/optimize/{workflow_id}/{node_id}/{prompt_field}",
        route.optimize_prompt,
        methods=["POST"],
        response_model=PromptOptimizeResponse,
    )
    return TestClient(app), state


def test_the_service_is_resolved_inside_the_new_scope_and_the_model_is_encoded(editor):
    client, state = editor

    response = client.post(f"/evaluate/{CONTEXT}", json=EVALUATE_BODY)

    assert response.status_code == 200
    assert state.calls == ["scope-enter", "resolve", "evaluate", "scope-exit"]
    assert response.json() == jsonable_encoder(EVALUATION)
    assert response.json()["provenance"]["ran_at"] == "2026-11-05T12:00:00Z"
    assert response.json()["provenance"]["deadline_hit"] is False


def test_a_budget_overrun_arrives_as_the_app_envelope(editor):
    client, state = editor
    state.fail = AppException(
        status_code=504,
        error_key=ErrorKey.PROMPT_EXECUTION_TIMEOUT,
        error_detail="The rewrite did not finish within the time budget.",
    )

    response = client.post(f"/optimize/{CONTEXT}", json=OPTIMIZE_BODY)

    assert response.status_code == 200
    assert response.json() == {
        "error": "The prompt check did not finish within the time budget.",
        "error_code": 504,
        "error_key": "PROMPT_EXECUTION_TIMEOUT",
        "error_detail": None,
    }


def test_a_bad_body_is_refused_before_the_stream(editor):
    client, state = editor

    response = client.post(f"/evaluate/{CONTEXT}", json={**EVALUATE_BODY, "techniques": []})

    assert response.status_code == 422
    assert state.calls == []
