"""
Everything a Datadog deployment needs from the app, behind one switch.

DATADOG_ENABLED=true (set only by deployments that ship to Datadog, e.g. PayByPhone):
- logs: one JSON object per stdout line, using Datadog's standard attribute names, so
  the level and fields are read without a log pipeline;
- traces: genassist.agent_id / workflow_id / conversation_id on the current span, read
  by ddtrace when DD_TRACE_OTEL_ENABLED=true;
- the same agent and conversation ids on every log line that follows in the request
  or task, so logs and traces filter the same way.

DATADOG_ENABLED unset or false (the default): nothing here runs. Logs keep the coloured
text format, and no span attributes or log fields are added.
"""

from __future__ import annotations

import json
import sys
import traceback
from typing import Any

from loguru import logger
from opentelemetry import trace as otel_trace

from app.core.config import logging as log_config
from app.core.config.settings import settings
from app.core.utils.sensitive_data_utils import redact_sensitive_substrings


# --------------------------------------------------------------------------- #
# JSON log lines
# --------------------------------------------------------------------------- #
def _known(value):
    """Context values default to "-" / -1 outside a request; leave those out."""
    return None if value in (None, "-", -1, "") else value


def _redact(text: str) -> str:
    return redact_sensitive_substrings(text) if log_config._REDACT_PII else text


# Datadog's own status values. Set explicitly so an ERROR line is never stored as info.
_DATADOG_STATUS = {
    "TRACE": "debug",
    "DEBUG": "debug",
    "INFO": "info",
    "SUCCESS": "info",
    "WARNING": "warn",
    "ERROR": "error",
    "CRITICAL": "critical",
}


def _datadog_status(level_name: str, level_no: int) -> str:
    if level_name in _DATADOG_STATUS:
        return _DATADOG_STATUS[level_name]
    # Custom levels: map by severity number, like the standard ones.
    return "critical" if level_no >= 50 else "error" if level_no >= 40 else "warn" if level_no >= 30 else "info" if level_no >= 20 else "debug"


def json_log_record(record: dict) -> dict:
    """Build one log event from a loguru record."""
    extra = record["extra"]
    event = {
        "timestamp": record["time"].isoformat(timespec="milliseconds"),
        "status": _datadog_status(record["level"].name, record["level"].no),
        "level": record["level"].name,
        "message": record["message"],
        "logger": {"name": record["name"], "method_name": record["function"], "line": record["line"]},
    }

    # Request context: a bound value (start/end lines) wins over the ContextVar
    # the middleware sets for everything logged while the request runs.
    def pick(key, ctx):
        return _known(extra.get(key)) or _known(ctx.get())

    if request_id := pick("request_id", log_config.request_id_ctx):
        event["request_id"] = request_id
    http = {
        "method": pick("method", log_config.method_ctx),
        "url_details": {"path": p} if (p := pick("path", log_config.path_ctx)) else None,
        "status_code": _known(extra.get("status")),
    }
    http = {k: v for k, v in http.items() if v is not None}
    if http:
        event["http"] = http
    if (duration := _known(extra.get("duration"))) is not None:
        try:
            event["duration_ms"] = float(duration)
        except (TypeError, ValueError):
            event["duration_ms"] = str(duration)  # never drop the line over a bad value
    if ip := pick("ip", log_config.ip_ctx):
        event["network"] = {"client": {"ip": ip}}
    if uid := pick("uid", log_config.uid_ctx):
        event["usr"] = {"id": str(uid)}
    for key, ctx in (("conversation_id", log_config.conversation_id_ctx), ("agent_id", log_config.agent_id_ctx)):
        if value := pick(key, ctx):
            event[key] = str(value)

    # logging.exception() outside an except block gives an empty (None, None, None)
    # exception; there is nothing to report then, so leave "error" out.
    if record["exception"] is not None and record["exception"].type is not None:
        exc_type, exc_value, _ = record["exception"]
        event["error"] = {
            "kind": exc_type.__name__,
            "message": _redact(str(exc_value)),
            "stack": _redact("".join(traceback.format_exception(*record["exception"]))),
        }
    return event


def json_stdout_sink(message) -> None:
    """One JSON object per line; tracebacks stay on the line of their message."""
    sys.stdout.write(json.dumps(json_log_record(message.record), default=str, ensure_ascii=False) + "\n")
    sys.stdout.flush()


# --------------------------------------------------------------------------- #
# The manager
# --------------------------------------------------------------------------- #
class DatadogObservability:
    """Datadog logs and trace tags, all off unless settings.DATADOG_ENABLED is true."""

    @property
    def enabled(self) -> bool:
        return bool(settings.DATADOG_ENABLED)

    def configure_logging(self) -> bool:
        """Add the JSON stdout sink when enabled. Returns False so the caller keeps its own console."""
        if not self.enabled:
            return False
        logger.add(json_stdout_sink, level=settings.LOG_LEVEL, filter=log_config._pii_filter, enqueue=False)
        return True

    def tag_agent(self, agent_id: Any, workflow_id: Any) -> None:
        """The chat endpoints find the agent from the API key, not the URL, so without
        these tags every agent's traffic looks the same in Datadog."""
        if not self.enabled:
            return
        span = otel_trace.get_current_span()
        if agent_id is not None:
            span.set_attribute("genassist.agent_id", str(agent_id))
            log_config.agent_id_ctx.set(str(agent_id))
        if workflow_id is not None:
            span.set_attribute("genassist.workflow_id", str(workflow_id))

    def tag_conversation(self, conversation_id: Any) -> None:
        """Lets every request and log line of one chat be found by its conversation id."""
        if not self.enabled or conversation_id is None:
            return
        otel_trace.get_current_span().set_attribute("genassist.conversation_id", str(conversation_id))
        log_config.conversation_id_ctx.set(str(conversation_id))


datadog_observability = DatadogObservability()
