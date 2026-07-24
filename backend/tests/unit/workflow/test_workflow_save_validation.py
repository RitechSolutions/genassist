"""Save-time sub-agent validation: topology first, then per-node config values"""

import pytest

from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.services.workflow import WorkflowService

_validate = WorkflowService._validate_sub_agents


def _sub(node_id, name, **data):
    return {"id": node_id, "type": "subAgentNode", "data": {"name": name, **data}}


def _deleg(child, parent):
    return {"source": child, "target": parent, "sourceHandle": "output_sub_agent", "targetHandle": "input_sub_agents"}


def test_noop_without_sub_agents():
    _validate({"nodes": [{"id": "a", "type": "agentNode", "data": {}}], "edges": []})


def test_draft_sub_agent_without_provider_saves():
    _validate({"nodes": [_sub("c", "Helper")], "edges": []})


def test_bad_timeout_rejected_with_config_key():
    with pytest.raises(AppException) as exc:
        _validate({"nodes": [_sub("c", "Helper", timeoutSeconds=999)], "edges": []})
    assert exc.value.status_code == 400
    assert exc.value.error_key == ErrorKey.SUB_AGENT_INVALID_CONFIG


def test_unsupported_type_rejected_with_config_key():
    with pytest.raises(AppException) as exc:
        _validate({"nodes": [_sub("c", "Helper", type="SimpleToolExecutor")], "edges": []})
    assert exc.value.error_key == ErrorKey.SUB_AGENT_INVALID_CONFIG


def test_topology_error_takes_precedence():
    nodes = [{"id": "p1", "type": "agentNode", "data": {}}, {"id": "p2", "type": "agentNode", "data": {}}, _sub("c", "Helper")]
    with pytest.raises(AppException) as exc:
        _validate({"nodes": nodes, "edges": [_deleg("c", "p1"), _deleg("c", "p2")]})
    assert exc.value.error_key == ErrorKey.SUB_AGENT_INVALID_TOPOLOGY
