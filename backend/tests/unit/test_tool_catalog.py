"""Unit tests for the shared workflow tool-catalogue resolver."""

import pytest

from app.services.tool_catalog import (
    build_agent_index,
    build_tool_index,
    nested_workflow_refs,
    resolve_agents,
    resolve_in_index,
)


def _agent(node_id, name):
    return {"id": node_id, "type": "agentNode", "data": {"name": name}}


def _tool(node_id, name, node_type="knowledgeBaseNode"):
    return {"id": node_id, "type": node_type, "data": {"name": name}}


def _tools_edge(tool_id, agent_id):
    return {"source": tool_id, "target": agent_id, "targetHandle": "tools"}


def test_single_agent_single_tool():
    wf = {
        "id": "wf1",
        "nodes": [_agent("a1", "Research Agent"), _tool("t1", "Knowledge Search")],
        "edges": [_tools_edge("t1", "a1")],
    }
    agents = resolve_agents(wf)
    assert len(agents) == 1
    agent = agents[0]
    assert agent["id"] == "a1"
    assert agent["label"] == "Research Agent"
    assert agent["tools"] == [
        {"id": "t1", "name": "knowledge_search", "label": "Knowledge Search", "type": "knowledgeBaseNode"}
    ]


def test_multiple_tools_one_agent_deduped():
    wf = {
        "nodes": [_agent("a1", "Agent"), _tool("t1", "Search"), _tool("t2", "Web")],
        "edges": [_tools_edge("t1", "a1"), _tools_edge("t2", "a1"), _tools_edge("t1", "a1")],
    }
    agents = resolve_agents(wf)
    assert len(agents) == 1
    assert {t["id"] for t in agents[0]["tools"]} == {"t1", "t2"}


def test_mcp_node_expands_to_composite_ids():
    mcp = {"id": "m1", "type": "mcpNode", "data": {"name": "MCP", "whitelistedTools": ["search", "fetch"]}}
    wf = {
        "nodes": [_agent("a1", "Agent"), mcp],
        "edges": [_tools_edge("m1", "a1")],
    }
    agents = resolve_agents(wf)
    tool_ids = {t["id"] for t in agents[0]["tools"]}
    assert tool_ids == {"m1:search", "m1:fetch"}


def test_two_agents_each_own_tools():
    wf = {
        "nodes": [
            _agent("a1", "A1"), _agent("a2", "A2"),
            _tool("t1", "T1"), _tool("t2", "T2"),
        ],
        "edges": [_tools_edge("t1", "a1"), _tools_edge("t2", "a2")],
    }
    agents = {a["id"]: a for a in resolve_agents(wf)}
    assert agents["a1"]["tools"][0]["id"] == "t1"
    assert agents["a2"]["tools"][0]["id"] == "t2"


def test_non_tools_edges_ignored():
    wf = {
        "nodes": [_agent("a1", "Agent"), _tool("t1", "T1")],
        "edges": [{"source": "t1", "target": "a1", "targetHandle": "input"}],
    }
    assert resolve_agents(wf) == []


def test_nested_workflow_refs():
    wf = {
        "nodes": [
            {"id": "x1", "type": "workflowExecutorNode", "data": {"name": "Child", "workflowId": "wf-child"}},
            {"id": "x2", "type": "workflowExecutorNode", "data": {"name": "NoId"}},
        ],
        "edges": [],
    }
    refs = nested_workflow_refs(wf)
    assert refs == [{"node_id": "x1", "label": "Child", "workflow_id": "wf-child"}]


def test_indexes_map_names_and_labels():
    wf = {
        "nodes": [_agent("a1", "Research Agent"), _tool("t1", "Knowledge Search")],
        "edges": [_tools_edge("t1", "a1")],
    }
    agents = resolve_agents(wf)
    tool_index = build_tool_index(agents)
    agent_index = build_agent_index(agents)
    # Case-insensitive resolution by label, snake name, and id.
    assert resolve_in_index(tool_index, "Knowledge Search", "tool") == "t1"
    assert resolve_in_index(tool_index, "KNOWLEDGE_SEARCH", "tool") == "t1"
    assert resolve_in_index(tool_index, "t1", "tool") == "t1"
    assert resolve_in_index(agent_index, "research agent", "agent") == "a1"
    assert resolve_in_index(tool_index, "nonexistent", "tool") is None


def test_duplicate_tool_name_is_ambiguous():
    wf = {
        "nodes": [_agent("a1", "Agent"), _tool("t1", "Search"), _tool("t2", "Search")],
        "edges": [_tools_edge("t1", "a1"), _tools_edge("t2", "a1")],
    }
    tool_index = build_tool_index(resolve_agents(wf))
    with pytest.raises(ValueError, match="ambiguous"):
        resolve_in_index(tool_index, "Search", "tool")
    # Each concrete id still resolves uniquely despite the shared name.
    assert resolve_in_index(tool_index, "t1", "tool") == "t1"
    assert resolve_in_index(tool_index, "t2", "tool") == "t2"


def test_mcp_node_exposes_composite_tool_ids():
    wf = {
        "nodes": [
            _agent("a1", "Agent"),
            {"id": "mcp1", "type": "mcpNode", "data": {"name": "MCP", "whitelistedTools": ["search", "fetch"]}},
        ],
        "edges": [_tools_edge("mcp1", "a1")],
    }
    agents = resolve_agents(wf)
    assert {tool["id"] for tool in agents[0]["tools"]} == {"mcp1:search", "mcp1:fetch"}
    # Legacy resolution maps the MCP tool name (case-insensitively) to its composite id.
    tool_index = build_tool_index(agents)
    assert resolve_in_index(tool_index, "search", "tool") == "mcp1:search"
    assert resolve_in_index(tool_index, "mcp1:fetch", "tool") == "mcp1:fetch"
