"""Unit tests for the Datadog integration (DATADOG_ENABLED): JSON log lines and trace tags.

Off by default, so other deployments keep text logs and get no Datadog fields.
"""

import asyncio
import json
import logging as stdlib_logging

import pytest
from loguru import logger

from app.core.config import logging as log_config
from app.core.config.settings import settings
from app.core.observability import datadog_observability
from app.core.observability.datadog_observability import json_stdout_sink


@pytest.fixture
def datadog_on(monkeypatch):
    monkeypatch.setattr(settings, "DATADOG_ENABLED", True)


@pytest.fixture
def json_lines(capsys):
    """Send loguru to the JSON stdout sink only, and return a reader for its lines."""
    # Sync tests share one context, so clear ids an earlier test may have set.
    cleared = [(var, var.set(None)) for var in (log_config.conversation_id_ctx, log_config.agent_id_ctx)]
    logger.remove()
    logger.configure(extra={"request_id": "-", "ip": "-", "method": "-", "path": "-", "uid": "-", "status": "-", "duration": "-"})
    logger.add(json_stdout_sink, level="DEBUG", filter=log_config._pii_filter)

    def read():
        return [json.loads(line) for line in capsys.readouterr().out.splitlines()]

    yield read
    for var, token in cleared:
        var.reset(token)
    log_config.init_logging()  # back to the configured sinks for other tests


def test_error_is_one_json_line_with_its_level(json_lines):
    logger.error("Agent returned an error")

    [event] = json_lines()
    assert event["level"] == "ERROR"
    assert event["message"] == "Agent returned an error"
    assert event["logger"]["method_name"] == "test_error_is_one_json_line_with_its_level"


def test_traceback_stays_on_the_same_line(json_lines, capsys):
    try:
        raise ValueError("bad input")
    except ValueError:
        logger.exception("Request failed")

    out = capsys.readouterr().out
    assert len(out.splitlines()) == 1
    event = json.loads(out)
    assert event["error"]["kind"] == "ValueError"
    assert event["error"]["message"] == "bad input"
    assert "Traceback (most recent call last)" in event["error"]["stack"]


def test_lines_outside_a_request_leave_request_fields_out(json_lines):
    logger.info("Celery task finished")

    [event] = json_lines()
    for key in ("request_id", "http", "network", "usr", "duration_ms", "conversation_id", "agent_id"):
        assert key not in event


def test_lines_inside_a_request_carry_its_context(json_lines):
    tokens = [
        (log_config.request_id_ctx, log_config.request_id_ctx.set("req-1")),
        (log_config.method_ctx, log_config.method_ctx.set("PATCH")),
        (log_config.path_ctx, log_config.path_ctx.set("/api/conversations/in-progress/update/c1")),
        (log_config.conversation_id_ctx, log_config.conversation_id_ctx.set("c1")),
        (log_config.agent_id_ctx, log_config.agent_id_ctx.set("a1")),
    ]
    try:
        logger.warning("Tool failed")
    finally:
        for var, token in tokens:
            var.reset(token)

    [event] = json_lines()
    assert event["request_id"] == "req-1"
    assert event["http"] == {"method": "PATCH", "url_details": {"path": "/api/conversations/in-progress/update/c1"}}
    assert event["conversation_id"] == "c1"
    assert event["agent_id"] == "a1"


def test_request_handled_line_has_status_and_duration(json_lines):
    logger.bind(request_id="req-2", method="GET", path="/api/health", status=200, duration="12.50", uid="u1").info(
        "Request handled 200"
    )

    [event] = json_lines()
    assert event["http"]["status_code"] == 200
    assert event["duration_ms"] == 12.5
    assert event["usr"] == {"id": "u1"}


def test_pii_is_redacted_in_message_and_error(json_lines, monkeypatch):
    monkeypatch.setattr(log_config, "_REDACT_PII", True)
    try:
        raise ValueError("Requester: Email: john@example.com is invalid")
    except ValueError:
        logger.exception("Zendesk rejected john@example.com")

    [event] = json_lines()
    assert "john@example.com" not in json.dumps(event)


def test_init_logging_writes_json_only_with_datadog_enabled(monkeypatch, capsys):
    monkeypatch.setattr(settings, "DATADOG_ENABLED", True)
    log_config.init_logging()
    capsys.readouterr()
    logger.info("hello")
    assert json.loads(capsys.readouterr().out)["message"] == "hello"

    monkeypatch.setattr(settings, "DATADOG_ENABLED", False)
    log_config.init_logging()
    capsys.readouterr()
    logger.info("hello")
    out = capsys.readouterr().out
    assert "hello" in out and not out.lstrip().startswith("{")


def test_datadog_is_off_by_default():
    assert type(settings).model_fields["DATADOG_ENABLED"].default is False


@pytest.mark.parametrize("raw, expected", [("true", True), ("1", True), ("false", False), ("0", False)])
def test_datadog_enabled_is_read_from_the_environment(monkeypatch, raw, expected):
    monkeypatch.setenv("DATADOG_ENABLED", raw)
    assert type(settings)().DATADOG_ENABLED is expected


def test_disabled_adds_no_trace_tags_and_no_log_ids(monkeypatch):
    from opentelemetry.sdk.trace import TracerProvider

    monkeypatch.setattr(settings, "DATADOG_ENABLED", False)

    async def chat_step():
        # asyncio.run copies the test thread's context; clear ids earlier sync tests set.
        log_config.conversation_id_ctx.set(None)
        log_config.agent_id_ctx.set(None)
        with TracerProvider().get_tracer(__name__).start_as_current_span("fastapi.request") as span:
            datadog_observability.tag_conversation("c-1")
            datadog_observability.tag_agent("a-1", "w-1")
        return span, log_config.conversation_id_ctx.get(), log_config.agent_id_ctx.get()

    span, conversation_id, agent_id = asyncio.run(chat_step())
    assert not any(k.startswith("genassist.") for k in span.attributes)
    assert (conversation_id, agent_id) == (None, None)


def test_trace_tags_also_set_the_log_ids(json_lines, datadog_on):
    async def chat_step():
        datadog_observability.tag_conversation("c-9")
        datadog_observability.tag_agent("a-9", None)
        logger.info("Agent replied")

    asyncio.run(chat_step())  # its own context, like a request or a Celery task
    logger.info("After the chat step")

    inside, after = json_lines()
    assert (inside["conversation_id"], inside["agent_id"]) == ("c-9", "a-9")
    assert "conversation_id" not in after and "agent_id" not in after


def test_conversation_route_logs_carry_the_id_and_the_next_request_does_not(json_lines, datadog_on):
    """The conversations router dependency sets the id before the route runs."""
    from fastapi import APIRouter, Depends, FastAPI
    from fastapi.testclient import TestClient

    from app.api.v1.routes import conversations as routes

    router = APIRouter(dependencies=[Depends(routes.tag_trace_with_conversation)])

    @router.get("/in-progress/{conversation_id}")
    async def poll(conversation_id: str):
        logger.info("Polling")
        return {}

    @router.get("/list")
    async def listing():
        logger.info("Listing")
        return {}

    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as client:
        client.get("/in-progress/0199e3a0-0000-7000-8000-0000000000c1")
        client.get("/list")

    events = {e["message"]: e for e in json_lines() if e["message"] in ("Polling", "Listing")}
    assert events["Polling"]["conversation_id"] == "0199e3a0-0000-7000-8000-0000000000c1"
    assert "conversation_id" not in events["Listing"]


def test_bad_bound_duration_does_not_drop_the_line(json_lines):
    logger.bind(duration="n/a").info("Odd duration")

    [event] = json_lines()
    assert event["message"] == "Odd duration"
    assert event["duration_ms"] == "n/a"


@pytest.mark.parametrize(
    "log, status",
    [
        (lambda: logger.debug("d"), "debug"),
        (lambda: logger.info("i"), "info"),
        (lambda: logger.success("s"), "info"),
        (lambda: logger.warning("w"), "warn"),
        (lambda: logger.error("e"), "error"),
        (lambda: logger.critical("c"), "critical"),
        (lambda: stdlib_logging.getLogger("app.test").error("stdlib e"), "error"),
        (lambda: stdlib_logging.getLogger("app.test").warning("stdlib w"), "warn"),
    ],
)
def test_every_level_gets_datadogs_status(json_lines, log, status):
    """Datadog reads `status`; an ERROR line must never land as info."""
    log()

    [event] = json_lines()
    assert event["status"] == status


def test_exception_logged_outside_an_except_block_has_no_error_block(json_lines):
    """logging.exception() with nothing raised used to give error: {kind: null, stack: "NoneType: None"}."""
    stdlib_logging.getLogger("app.services.auth").exception("JWT error: Not enough segments")

    [event] = json_lines()
    assert event["status"] == "error"
    assert "error" not in event


def test_stdlib_log_lines_name_the_function_that_logged(json_lines):
    """The stdlib bridge used a fixed frame depth, so logging.exception() named the logging module."""

    def check_token():
        stdlib_logging.getLogger("app.services.auth").exception("JWT error")
        stdlib_logging.getLogger("app.services.auth").error("plain error")

    check_token()

    for event in json_lines():
        assert event["logger"]["method_name"] == "check_token"
        assert event["logger"]["name"] == __name__
