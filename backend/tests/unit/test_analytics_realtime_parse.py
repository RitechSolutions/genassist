"""Unit tests for analytics_realtime.parse_agent_response_for_stats.

Pure parsing logic (no DB) that turns a raw agent_response payload into the
data dict the incremental-stats repository methods consume.
"""

from datetime import datetime, timezone
from uuid import UUID

from app.services.analytics_realtime import parse_agent_response_for_stats

_AGENT_ID = "019f60f3-5c20-715c-850b-ffc8f458ee30"


def test_returns_none_when_agent_id_missing():
    assert parse_agent_response_for_stats({}) is None
    assert parse_agent_response_for_stats({"status": "success"}) is None


def test_returns_none_when_agent_id_invalid():
    assert parse_agent_response_for_stats({"agent_id": "not-a-uuid"}) is None


def test_minimal_success_payload():
    data = parse_agent_response_for_stats({"agent_id": _AGENT_ID, "status": "success"})
    assert data is not None
    assert data["agent_id"] == UUID(_AGENT_ID)
    assert data["is_success"] is True
    assert data["response_ms"] is None
    assert data["rag_used"] is False
    assert data["nodes"] == []
    assert data["total_nodes_executed"] == 0
    assert data["stat_date"] == datetime.now(timezone.utc).date()


def test_failed_status_is_not_success():
    data = parse_agent_response_for_stats({"agent_id": _AGENT_ID, "status": "failed"})
    assert data is not None
    assert data["is_success"] is False


def test_completed_status_counts_as_success():
    data = parse_agent_response_for_stats({"agent_id": _AGENT_ID, "status": "completed"})
    assert data["is_success"] is True


def test_parses_response_time_and_rag():
    payload = {
        "agent_id": _AGENT_ID,
        "status": "success",
        "rag_used": True,
        "row_agent_response": {
            "performance_metrics": {"totalExecutionTime": "1234.5"},
        },
    }
    data = parse_agent_response_for_stats(payload)
    assert data["response_ms"] == 1234.5
    assert data["rag_used"] is True


def test_parses_nodes_from_dict_status_map():
    payload = {
        "agent_id": _AGENT_ID,
        "status": "success",
        "row_agent_response": {
            "state": {
                "nodeExecutionStatus": {
                    "n1": {"type": "llm", "status": "success", "time_taken": "50"},
                    "n2": {"type": "tool", "status": "failed", "execution_time_ms": 20},
                }
            }
        },
    }
    data = parse_agent_response_for_stats(payload)
    assert data["total_nodes_executed"] == 2
    by_type = {n["type"]: n for n in data["nodes"]}
    assert by_type["llm"]["is_success"] is True
    assert by_type["llm"]["execution_ms"] == 50.0
    assert by_type["tool"]["is_success"] is False
    assert by_type["tool"]["execution_ms"] == 20.0


def test_parses_tokens_and_cost():
    payload = {
        "agent_id": _AGENT_ID,
        "status": "success",
        "token_usage": {"input_tokens": 10, "output_tokens": 20},
        "cost_usd": 0.0031,
    }
    data = parse_agent_response_for_stats(payload)
    assert data["input_tokens"] == 10
    assert data["output_tokens"] == 20
    assert data["cost_usd"] == 0.0031


def test_bad_response_time_is_ignored():
    payload = {
        "agent_id": _AGENT_ID,
        "status": "success",
        "row_agent_response": {"performance_metrics": {"totalExecutionTime": "abc"}},
    }
    data = parse_agent_response_for_stats(payload)
    assert data["response_ms"] is None


_DIAGNOSTICS = {"child": {"requested": True, "applied": False}}


def _payload(**state_extra):
    return {
        "agent_id": _AGENT_ID,
        "status": "success",
        "row_agent_response": {
            "state": {
                "nodeExecutionStatus": {
                    "n1": {"type": "llm", "status": "success", "time_taken": "50"},
                    "n2": {"type": "tool", "status": "failed", "execution_time_ms": 20},
                },
                **state_extra,
            }
        },
    }


def test_propagated_prompt_caching_diagnostics_do_not_change_node_stats():
    plain = parse_agent_response_for_stats(_payload())
    annotated = parse_agent_response_for_stats(_payload(promptCachingDiagnostics=_DIAGNOSTICS))

    assert annotated["total_nodes_executed"] == plain["total_nodes_executed"] == 2
    assert annotated["nodes"] == plain["nodes"]
    assert annotated["is_success"] == plain["is_success"]
