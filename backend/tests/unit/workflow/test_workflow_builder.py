"""Workflow Builder: node catalog, graph validation, draft operations, spec build and layout."""

import asyncio
import json

import pytest

from app.modules.workflow.builder import catalog
from app.modules.workflow.builder.build import SpecValidationError, build_workflow_from_spec
from app.modules.workflow.builder.draft import (
    ORIGIN_CANVAS,
    SECRET_PLACEHOLDER,
    STATUS_READY,
    DraftError,
    WorkflowDraft,
    make_edge,
)
from app.modules.workflow.builder.layout import auto_layout, place_new_nodes
from app.modules.workflow.builder.validation import validate_workflow


def codes(issues, severity=None):
    return {i.code for i in issues if severity is None or i.severity == severity}


def finalize(draft: WorkflowDraft, summary: str = ""):
    """Finalize as if the builder had just test-run the draft (a run is required first)."""
    draft.needs_test = False
    return draft.finalize(summary)


def chatbot() -> WorkflowDraft:
    """Start -> agent -> reply."""
    draft = WorkflowDraft()
    draft.add_node("chatInputNode", "Start")
    draft.add_node("agentNode", "Assistant", {"systemPrompt": "Help the user."}, connect_from="n1")
    draft.add_node("chatOutputNode", "Reply", connect_from="n2")
    return draft


# ── Catalog ───────────────────────────────────────────────────────────────


def test_catalog_covers_canvas_nodes_missing_from_backend_schemas():
    for node_type in ("setStateNode", "mcpNode", "workflowExecutorNode", "fileReaderNode", "externalAgentNode"):
        assert catalog.is_known(node_type)
        assert catalog.handlers_for(node_type)


def test_switch_handles_follow_cases():
    data = {"cases": [{"id": "case_1", "label": "A", "value": "a"}, {"id": "case_7", "label": "B", "value": "b"}]}
    assert catalog.handle_ids("switchNode", data, "source") == ["output_case_1", "output_case_7", "output_default"]


def test_search_nodes_finds_by_purpose_and_schema_is_small():
    assert catalog.search_nodes("zendesk ticket")[0]["type"] == "zendeskTicketNode"
    assert catalog.search_nodes("knowledge base")[0]["type"] == "knowledgeBaseNode"
    assert all(len(catalog.node_schema_text(t)) < 4000 for t in catalog.all_node_types())


def test_unknown_node_type_suggests_closest():
    assert "slackMessageNode" in catalog.node_schema_text("slackNode")


# ── Draft operations ──────────────────────────────────────────────────────


def test_chatbot_draft_is_valid_and_finalizes():
    draft = chatbot()
    assert not codes(draft.issues(), "error")
    finalize(draft, "A simple chatbot")
    assert draft.status == STATUS_READY


def test_builder_defaults_and_provider_are_applied():
    draft = WorkflowDraft()
    draft.defaults = {"providerId": "provider-1"}
    draft.add_node("chatInputNode", "Start")
    agent = draft.find(draft.add_node("agentNode", "Assistant", connect_from="n1")["node_id"])
    assert agent["data"]["type"] == "ReActAgentLC"
    assert agent["data"]["userPrompt"] == "{{session.message}}"
    assert agent["data"]["providerId"] == "provider-1"


def test_unknown_node_type_and_config_key_are_rejected_without_side_effects():
    draft = chatbot()
    with pytest.raises(DraftError, match="slackMessageNode"):
        draft.add_node("slackNode", "x")
    with pytest.raises(DraftError, match="no config field"):
        draft.add_node("jiraNode", "Jira", {"operation": "create_issue"})
    with pytest.raises(DraftError, match="not a valid matchMode"):
        draft.add_node("switchNode", "S", {"matchMode": "fuzzy"})
    assert len(draft.nodes) == 3
    # A rejected add does not burn an alias.
    assert draft.add_node("templateNode", "T", {"template": "hi"})["alias"] == "n4"


def test_add_node_with_bad_connection_adds_nothing():
    draft = chatbot()
    with pytest.raises(DraftError, match="already receives input"):
        draft.add_node("templateNode", "T", {"template": "x"}, connect_to="n3")
    assert len(draft.nodes) == 3


def test_insert_between_two_nodes_replaces_their_connection():
    draft = chatbot()
    draft.add_node("templateNode", "Format", {"template": "{{source.message}}"}, connect_from="n2", connect_to="n3")
    edges = {(draft.alias(e["source"]), draft.alias(e["target"])) for e in draft.edges}
    assert edges == {("n1", "n2"), ("n2", "n4"), ("n4", "n3")}
    assert not codes(draft.issues(), "error")


def test_connect_requires_named_output_on_multi_output_nodes():
    draft = WorkflowDraft()
    draft.add_node("chatInputNode", "Start")
    draft.add_node("routerNode", "Check", {"first_value": "{{session.message}}", "second_value": "x"}, connect_from="n1")
    draft.add_node("templateNode", "Yes", {"template": "yes"})
    with pytest.raises(DraftError, match="several outputs"):
        draft.connect("n2", "n3")
    draft.connect("n2.output_true", "n3")
    with pytest.raises(DraftError, match="no output 'output_maybe'"):
        draft.connect("n2.output_maybe", "n3")


def test_single_input_rule_is_enforced_except_for_aggregator():
    draft = chatbot()
    draft.add_node("templateNode", "Other", {"template": "x"})
    with pytest.raises(DraftError, match="already receives input"):
        draft.connect("n4", "n3")
    draft.add_node("aggregatorNode", "Merge")
    draft.disconnect("n2", "n3")
    draft.connect("n2", "n5")
    draft.connect("n4", "n5")


def test_add_tool_creates_tool_builder_node_and_both_edges():
    draft = chatbot()
    result = draft.add_tool(
        "n2", "zendeskTicketNode", "Create Ticket", "Open a ticket.",
        config={"subject": "{{source.subject}}"},
        parameters={"subject": "Ticket title"},
    )
    tool = draft.find(result["tool"])
    wrapped = draft.find(result["node"])
    assert tool["type"] == "toolBuilderNode"
    assert json.loads(tool["data"]["forwardTemplate"]) == {"source.subject": "{{direct_input.parameters.subject}}"}
    assert tool["data"]["inputSchema"]["subject"]["required"] is True
    handles = {(e["sourceHandle"], e["targetHandle"]) for e in draft.edges if e["source"] == tool["id"]}
    assert handles == {("output_tool", "input_tools"), ("starter_processor", "input")}
    assert wrapped["data"]["subject"] == "{{source.subject}}"
    assert not codes(draft.issues(), "error")
    assert [c["op"] for c in draft.changes][-1] == "add_tool"


def test_add_tool_failure_rolls_everything_back():
    draft = chatbot()
    before = (len(draft.nodes), len(draft.edges), draft.revision, draft.next_alias)
    with pytest.raises(DraftError):
        draft.add_tool("n2", "zendeskTicketNode", "T", "d", config={"nope": 1})
    with pytest.raises(DraftError, match="cannot use tools"):
        draft.add_tool("n1", "knowledgeBaseNode", "T", "d")
    assert (len(draft.nodes), len(draft.edges), draft.revision, draft.next_alias) == before


def test_knowledge_base_tool_gets_a_query_parameter_by_default():
    draft = chatbot()
    result = draft.add_tool("n2", "knowledgeBaseNode", "Search", "Search the docs.")
    assert draft.find(result["node"])["data"]["query"] == "{{source.query}}"
    assert "query" in draft.find(result["tool"])["data"]["inputSchema"]


def test_sub_agent_connects_on_delegation_handles():
    draft = chatbot()
    draft.add_node(
        "subAgentNode", "Refunds", {"description": "Handles refunds.", "systemPrompt": "..."}, connect_to="n2"
    )
    edge = draft.edges[-1]
    assert (edge["sourceHandle"], edge["targetHandle"]) == ("output_sub_agent", "input_sub_agents")
    assert not codes(draft.issues(), "error")


def test_switch_case_update_recomputes_handles_and_drops_stale_edges():
    draft = WorkflowDraft()
    draft.add_node("chatInputNode", "Start")
    draft.add_node(
        "switchNode", "Route",
        {"switchValue": "{{session.message}}", "cases": [{"label": "A", "value": "a"}, {"label": "B", "value": "b"}]},
        connect_from="n1",
    )
    draft.add_node("templateNode", "A", {"template": "a"}, connect_from="n2.output_case_1")
    draft.add_node("templateNode", "B", {"template": "b"}, connect_from="n2.output_case_2")

    result = draft.update_node("n2", {"cases": [{"label": "B", "value": "bee"}, {"label": "C", "value": "c"}]})
    switch = draft.find("n2")
    # "B" keeps its id (and its edge); "A" is gone with its edge; "C" gets a fresh id.
    assert [c["id"] for c in switch["data"]["cases"]] == ["case_2", "case_3"]
    assert "n2.output_case_1 -> n3.input" in result["message"]
    assert {e["sourceHandle"] for e in draft.edges if e["source"] == switch["id"]} == {"output_case_2"}


def test_removing_a_tool_removes_the_node_it_runs():
    draft = chatbot()
    result = draft.add_tool("n2", "knowledgeBaseNode", "Search", "Search the docs.")
    draft.remove_node(result["tool"])
    assert len(draft.nodes) == 3 and len(draft.edges) == 2


def test_finalize_is_blocked_while_errors_remain():
    draft = WorkflowDraft()
    draft.add_node("chatInputNode", "Start")
    draft.add_node("agentNode", "Assistant", {"systemPrompt": "Help."}, connect_from="n1")
    with pytest.raises(DraftError, match="dead_end|no_output_node"):
        finalize(draft)
    draft.add_node("chatOutputNode", "Reply", connect_from="n2")
    finalize(draft)


# ── Outline ───────────────────────────────────────────────────────────────


def test_outline_is_compact_and_hides_noise():
    draft = chatbot()
    draft.update_node("n2", {"systemPrompt": "x" * 5000})
    draft.add_tool("n2", "knowledgeBaseNode", "Search", "Search the docs.")
    outline = draft.render_outline()
    assert len(outline) < 1500
    assert "<5000 chars" in outline
    for noise in ("handlers", "position", "forwardTemplate", draft.nodes[0]["id"]):
        assert noise not in outline
    assert "parameters=[\"query\"]" in outline
    assert "x" * 5000 in draft.render_node("n2")


def test_outline_masks_secrets_and_placeholder_is_never_written_back():
    draft = chatbot()
    draft.add_tool("n2", "jiraNode", "Jira", "Create a task.", config={"apiToken": "super-secret"})
    assert "super-secret" not in draft.render_outline()
    jira = next(n for n in draft.nodes if n["type"] == "jiraNode")
    assert "super-secret" not in draft.render_node(draft.alias(jira["id"]))
    draft.update_node(draft.alias(jira["id"]), {"apiToken": SECRET_PLACEHOLDER, "spaceKey": "OPS"})
    assert jira["data"]["apiToken"] == "super-secret"
    assert jira["data"]["spaceKey"] == "OPS"


def test_node_output_references_use_aliases_both_ways():
    draft = chatbot()
    draft.add_node("templateNode", "Echo", {"template": "{{node_outputs.n2.message}}"}, connect_from="n2", connect_to="n3")
    template = draft.find("n4")
    agent_id = draft.find("n2")["id"]
    assert template["data"]["template"] == f"{{{{node_outputs.{agent_id}.message}}}}"
    assert "{{node_outputs.n2.message}}" in draft.render_outline()


# ── Canvas round trip ─────────────────────────────────────────────────────


def test_canvas_draft_keeps_ids_and_reports_only_new_issues():
    canvas = chatbot().to_canvas()
    # A problem the user already has: an orphan agent with no prompt.
    canvas["nodes"].append({"id": "orphan", "type": "agentNode", "position": {"x": 0, "y": 900},
                            "data": {"name": "Orphan", "handlers": catalog.handlers_for("agentNode")}})
    draft = WorkflowDraft.from_canvas(canvas["nodes"], canvas["edges"])
    assert draft.origin == ORIGIN_CANVAS
    assert {n["id"] for n in draft.nodes} == {n["id"] for n in canvas["nodes"]}
    assert draft.issues() and not draft.new_issues()

    draft.update_node("n2", {"systemPrompt": "Be brief."})
    finalize(draft)  # pre-existing problems do not block the user's edit
    payload = draft.client_payload()
    assert all(i["pre_existing"] for i in payload["issues"])
    assert payload["changes"][0]["op"] == "update_node"


def test_aliases_stay_stable_across_turns():
    first = chatbot()
    first.add_node("templateNode", "Extra", {"template": "x"})
    canvas = first.to_canvas()
    canvas["nodes"] = [n for n in canvas["nodes"] if n["data"]["name"] != "Assistant"]
    second = WorkflowDraft.from_canvas(canvas["nodes"], [], previous=first)
    assert second.alias(first.find("n4")["id"]) == "n4"
    assert second.add_node("templateNode", "New", {"template": "y"})["alias"] == "n5"


def test_draft_serialization_round_trip():
    draft = chatbot()
    finalize(draft, "done")
    restored = WorkflowDraft.from_dict(json.loads(json.dumps(draft.to_dict())))
    assert restored.render_outline() == draft.render_outline()
    assert restored.status == STATUS_READY and restored.aliases == draft.aliases


def test_new_nodes_are_placed_without_moving_existing_ones():
    canvas = chatbot().to_canvas()
    before = {n["id"]: dict(n["position"]) for n in canvas["nodes"]}
    draft = WorkflowDraft.from_canvas(canvas["nodes"], canvas["edges"])
    added = draft.add_tool("n2", "knowledgeBaseNode", "Search", "Search the docs.")
    after = {n["id"]: n["position"] for n in draft.to_canvas()["nodes"]}
    assert all(after[i] == before[i] for i in before)
    positions = [tuple(p.values()) for p in after.values()]
    assert len(set(positions)) == len(positions)
    assert after[draft.find(added["tool"])["id"]]["y"] > before[draft.find("n2")["id"]]["y"]


# ── Validation ────────────────────────────────────────────────────────────


def _node(node_id, node_type, **data):
    return {"id": node_id, "type": node_type, "data": {"name": node_id, **catalog.default_data(node_type), **data}}


def test_validation_flags_structural_mistakes():
    nodes = [
        _node("in", "chatInputNode"),
        _node("agent", "agentNode", systemPrompt="x"),
        _node("out", "chatOutputNode"),
        {"id": "ghost", "type": "notARealNode", "data": {"name": "g"}},
        _node("tool", "toolBuilderNode"),
        _node("tpl", "templateNode", template="{{node_outputs.missing.x}} {{session.undeclared}}"),
    ]
    edges = [
        make_edge("in", "agent", "output", "input"),
        make_edge("agent", "out", "output", "input"),
        make_edge("in", "out", "output", "input"),            # second input into "out"
        make_edge("agent", "tpl", "output_nope", "input"),     # handle that does not exist
        make_edge("tool", "tpl", "output_tool", "input"),      # tool handle into a plain input
        make_edge("agent", "nowhere", "output", "input"),      # unknown node
    ]
    found = codes(validate_workflow(nodes, edges))
    assert {
        "unknown_node_type", "multiple_inputs", "unknown_source_handle", "incompatible_handles",
        "edge_unknown_node", "tool_not_attached", "unknown_node_reference", "unknown_session_variable",
    } <= found


def test_validation_flags_cycles_missing_entry_and_dead_ends():
    nodes = [_node("a", "templateNode", template="a"), _node("b", "templateNode", template="b")]
    edges = [make_edge("a", "b", "output", "input"), make_edge("b", "a", "output", "input")]
    assert {"cycle", "no_entry_node"} <= codes(validate_workflow(nodes, edges))

    nodes = [_node("in", "chatInputNode"), _node("agent", "agentNode", systemPrompt="x")]
    found = codes(validate_workflow(nodes, [make_edge("in", "agent", "output", "input")]), "error")
    assert {"no_output_node", "dead_end"} <= found


def test_missing_provider_and_knowledge_base_are_setup_not_errors():
    draft = chatbot()
    draft.add_tool("n2", "knowledgeBaseNode", "Search", "Search the docs.")
    issues = draft.issues()
    assert not codes(issues, "error")
    assert {(i.field) for i in issues if i.severity == "setup"} == {"providerId", "selectedBases"}


# ── Spec build ────────────────────────────────────────────────────────────

KB_SPEC = {
    "workflow": [
        {"uniqueId": "1", "node_name": "chatInputNode", "function_of_node": "Chat Input"},
        {"uniqueId": "2", "node_name": "agentNode", "function_of_node": "Support Agent",
         "config": {"systemPrompt": "Help.", "userPrompt": "{{source.message}}"}},
        {"uniqueId": "3", "node_name": "chatOutputNode", "function_of_node": "Chat Output"},
        {"uniqueId": "4", "node_name": "toolBuilderNode", "function_of_node": "KB Tool",
         "config": {"name": "KB", "description": "Search the KB"}},
        {"uniqueId": "5", "node_name": "knowledgeBaseNode", "function_of_node": "KB",
         "config": {"query": "{{session.message}}", "limit": 5}},
    ],
    "edges": [
        {"from": "1", "to": "2"},
        {"from": "2", "to": "3"},
        {"from": "4", "to": "2", "sourceHandle": "output_tool", "targetHandle": "input_tools"},
        {"from": "4", "to": "5", "sourceHandle": "starter_processor", "targetHandle": "input"},
    ],
}


def test_build_from_spec_produces_canvas_ready_workflow():
    built = build_workflow_from_spec(KB_SPEC, "KB bot", defaults={"providerId": "p1"})
    assert len(built["nodes"]) == 5 and len(built["edges"]) == 4
    agent = next(n for n in built["nodes"] if n["type"] == "agentNode")
    assert agent["data"]["providerId"] == "p1"
    assert {h["id"] for h in agent["data"]["handlers"]} >= {"input", "input_tools", "output"}
    assert not codes(validate_workflow(built["nodes"], built["edges"]), "error")


def test_build_from_spec_without_edges_chains_nodes():
    spec = {"workflow": [n for n in KB_SPEC["workflow"][:3]]}
    built = build_workflow_from_spec(spec, "chain")
    assert len(built["edges"]) == 2


def test_build_from_spec_rejects_invalid_specs_with_actionable_issues():
    spec = json.loads(json.dumps(KB_SPEC))
    spec["workflow"][1]["node_name"] = "superAgentNode"
    spec["workflow"].append({"uniqueId": "6", "node_name": "setStateNode", "function_of_node": "Save",
                             "config": {"values": [{"key": "a", "value": "b"}]}})
    with pytest.raises(SpecValidationError) as excinfo:
        build_workflow_from_spec(spec, "bad")
    messages = " | ".join(i["message"] for i in excinfo.value.issues)
    assert "Unknown node type 'superAgentNode'" in messages
    assert "setStateNode has no config field(s) ['values']" in messages
    assert all({"node", "field", "message"} <= set(i) for i in excinfo.value.issues)


def test_build_from_spec_rejects_bad_handles_and_dead_ends():
    spec = json.loads(json.dumps(KB_SPEC))
    spec["edges"][1] = {"from": "2", "to": "3", "sourceHandle": "output_true"}
    with pytest.raises(SpecValidationError, match="no output 'output_true'"):
        build_workflow_from_spec(spec, "bad")


# ── Layout ────────────────────────────────────────────────────────────────


def test_auto_layout_terminates_on_cycles():
    nodes = [{"id": str(i), "type": "templateNode", "data": {}} for i in range(4)]
    edges = [
        {"source": "0", "target": "1"},
        {"source": "1", "target": "2"},
        {"source": "2", "target": "1", "targetHandle": "input_loop"},  # loop back-edge
        {"source": "1", "target": "3"},
    ]
    laid_out = auto_layout(nodes, edges)
    assert all("position" in n for n in laid_out)
    assert laid_out[0]["position"]["x"] < laid_out[1]["position"]["x"] < laid_out[2]["position"]["x"]


def test_place_new_nodes_resolves_group_relative_positions():
    nodes = [
        {"id": "g", "type": "groupNode", "position": {"x": 1000, "y": 1000}, "data": {}},
        {"id": "a", "type": "templateNode", "parentId": "g", "position": {"x": 10, "y": 20}, "data": {}},
        {"id": "new", "type": "templateNode", "position": {"x": 0, "y": 0}, "data": {}},
    ]
    placed = place_new_nodes(nodes, [{"source": "a", "target": "new"}], {"new"})
    assert placed[2]["position"] == {"x": 1360, "y": 1020}
    assert placed[1]["position"] == {"x": 10, "y": 20}


# ── Tools ─────────────────────────────────────────────────────────────────


def test_tools_build_a_workflow_and_report_errors_as_text(monkeypatch):
    from app.modules.workflow.builder import tools

    store = {}

    async def fake_load(thread_id):
        return WorkflowDraft.from_dict(json.loads(store[thread_id])) if thread_id in store else None

    async def fake_save(thread_id, draft):
        store[thread_id] = json.dumps(draft.to_dict())

    monkeypatch.setattr(tools, "load_draft", fake_load)
    monkeypatch.setattr(tools, "save_draft", fake_save)

    async def scenario():
        run = lambda tool, **args: tools.run_tool("t1", tool, args)
        assert "empty" in await run("get_workflow")
        assert "t1" not in store  # reading never creates a draft
        plan = lambda *ops: json.dumps(list(ops))
        await run("apply_plan", operations=plan({"op": "add_node", "node_type": "chatInputNode", "name": "Start"}))
        bad = await run("apply_plan", operations=plan({"op": "add_node", "node_type": "agentNode", "name": "A", "connect_from": "n9"}))
        assert "FAILED: No node 'n9'" in bad
        # Parallel tool calls must not lose each other's writes.
        await asyncio.gather(
            run("apply_plan", operations=plan({"op": "add_node", "node_type": "agentNode", "name": "A", "system_prompt": "x", "connect_from": "n1"})),
            run("apply_plan", operations=plan({"op": "add_node", "node_type": "templateNode", "name": "T", "config": {"template": "t"}})),
        )
        outline = await run("get_workflow")
        assert "agentNode" in outline and "templateNode" in outline
        assert (await run("finalize_workflow")).startswith("ERROR:")
        zendesk = await run("lookup_node", query="zendesk ticket")
        assert "zendeskTicketNode" in zendesk and "Details of zendeskTicketNode" in zendesk
        assert "cases" in await run("lookup_node", query="switchNode")
        assert "intent_routing" in await run("get_pattern")

    asyncio.run(scenario())


def test_every_tool_definition_is_dispatchable():
    from app.modules.workflow.builder.tools import TOOL_DEFINITIONS, _apply

    draft = chatbot()
    for definition in TOOL_DEFINITIONS:
        if definition["name"] in ("lookup_node", "get_pattern", "list_resources"):
            continue
        try:
            _apply(draft, definition["name"], {})
        except DraftError:
            pass  # missing arguments are reported, not crashed on


# ── Builder tools node and the seeded builder workflow ────────────────────


class _State:
    def get_thread_id(self):
        return "thread-1"


def test_builder_tools_node_exposes_one_tool_per_definition():
    from app.modules.workflow.builder.tools import TOOL_NAMES
    from app.modules.workflow.engine.nodes import WorkflowBuilderToolsNode
    from app.modules.workflow.engine.workflow_engine import WorkflowEngine

    WorkflowEngine({"nodes": [], "edges": []})
    assert WorkflowEngine._node_registry["workflowBuilderToolsNode"] is WorkflowBuilderToolsNode

    node = WorkflowBuilderToolsNode("tools", {"data": {"name": "Workflow Builder Tools"}}, _State())
    tools = node.get_tools()
    assert [t.name for t in tools] == TOOL_NAMES
    assert all(t.node_id == f"tools:{t.name}" for t in tools)
    # Parameters are in the shape agents turn into a tool schema.
    plan_tool = next(t for t in tools if t.name == "apply_plan")
    assert plan_tool.parameters["operations"]["required"] is True
    assert "add_tool" in plan_tool.description and "$name" in plan_tool.description

    limited = WorkflowBuilderToolsNode("tools", {"data": {"enabledTools": ["get_workflow"]}}, _State())
    assert [t.name for t in limited.get_tools()] == ["get_workflow"]


def test_tool_catalog_lists_builder_tools_for_the_agent():
    from app.modules.workflow.builder.tools import TOOL_NAMES
    from app.services.tool_catalog import resolve_agents

    workflow = {
        "nodes": [
            {"id": "agent", "type": "agentNode", "data": {"name": "Builder"}},
            {"id": "tools", "type": "workflowBuilderToolsNode", "data": {"name": "Workflow Builder Tools"}},
        ],
        "edges": [make_edge("tools", "agent", "output_tool", "input_tools")],
    }
    (agent,) = resolve_agents(workflow)
    assert [t["id"] for t in agent["tools"]] == [f"tools:{name}" for name in TOOL_NAMES]


def test_seeded_builder_workflow_is_current_and_valid():
    import re
    from pathlib import Path

    from app.db.seed.knowledge.generate_workflow_builder_workflow import OUTPUT_PATH, build_workflow

    seeded = json.loads(Path(OUTPUT_PATH).read_text())
    assert seeded == json.loads(json.dumps(build_workflow())), (
        "workflow_builder_wf_data.json is stale; run "
        "python -m app.db.seed.knowledge.generate_workflow_builder_workflow"
    )
    assert not validate_workflow(seeded["nodes"], seeded["edges"])

    prompt = next(n for n in seeded["nodes"] if n["type"] == "agentNode")["data"]["systemPrompt"]
    # The engine substitutes {{...}} in node config, so the prompt must not contain any.
    assert not re.findall(r"{{[^\s{}]+}}", prompt)
    # Every tool the prompt tells the agent to call exists.
    from app.modules.workflow.builder.tools import TOOL_NAMES

    for name in ("get_workflow", "lookup_node", "get_pattern", "apply_plan", "get_node", "set_node_field",
                 "test_workflow", "get_last_test_run", "finalize_workflow"):
        assert name in prompt and name in TOOL_NAMES
    # Every tool the agent has is one the prompt tells it about.
    assert all(name in prompt for name in TOOL_NAMES)


def test_patterns_reference_only_real_node_types_and_config_fields():
    """The recipes are the agent's examples; a field that does not exist would teach it to hallucinate."""
    import re

    from app.modules.workflow.builder.patterns import PATTERNS

    for name, pattern in PATTERNS.items():
        for op in pattern.get("plan") or []:
            if op.get("node_type"):
                assert catalog.is_known(op["node_type"]), f"{name}: unknown node type {op['node_type']}"


# ── Writing prompts and single fields ─────────────────────────────────────


def test_system_prompt_argument_and_missing_field_hint():
    draft = WorkflowDraft()
    draft.add_node("chatInputNode", "Start")
    bare = draft.add_node("agentNode", "Assistant", connect_from="n1")
    assert "Still required" in bare["message"] and "systemPrompt" in bare["message"]

    ok = draft.add_node("llmModelNode", "Classifier", system_prompt="Reply with one word.")
    assert "Still required" not in ok["message"]
    assert draft.find(ok["alias"])["data"]["systemPrompt"] == "Reply with one word."

    with pytest.raises(DraftError, match="no system prompt"):
        draft.add_node("templateNode", "T", system_prompt="x")


def test_set_field_writes_long_text_verbatim_and_parses_non_text_fields():
    draft = chatbot()
    prompt = 'You are "Parker".\nRules:\n- say {{session.message}} back\n- never use \\ or } carelessly'
    draft.set_field("n2", "systemPrompt", prompt)
    agent = draft.find("n2")
    assert agent["data"]["systemPrompt"] == prompt

    draft.set_field("n2", "maxIterations", "12")
    draft.set_field("n2", "memory", "false")
    assert agent["data"]["maxIterations"] == 12 and agent["data"]["memory"] is False
    draft.set_field("n2", "name", "Parker")
    assert agent["data"]["name"] == "Parker"

    with pytest.raises(DraftError, match="no config field"):
        draft.set_field("n2", "prompt", "x")
    with pytest.raises(DraftError, match="send its value as JSON"):
        draft.set_field("n2", "maxIterations", "a lot")


def test_structured_tool_arguments_are_declared_as_text():
    """Free-form object arguments get left empty by models; they must be JSON text."""
    from app.modules.workflow.builder.tools import TOOL_DEFINITIONS

    for definition in TOOL_DEFINITIONS:
        for name, spec in definition["parameters"].items():
            assert spec["type"] == "string", f"{definition['name']}.{name}"


def test_config_and_parameters_are_accepted_as_json_text():
    draft = chatbot()
    draft.update_node("n2", '{"maxIterations": 9}')
    assert draft.find("n2")["data"]["maxIterations"] == 9
    result = draft.add_tool(
        "n2", "slackMessageNode", "Notify", "Post to the channel.",
        config='{"message": "{{source.text}}"}', parameters='{"text": "What to post"}',
    )
    assert "text" in draft.find(result["tool"])["data"]["inputSchema"]
    with pytest.raises(DraftError, match="must be a JSON object"):
        draft.update_node("n2", "{not json")


# ── Test runs ─────────────────────────────────────────────────────────────


def test_test_run_reports_response_steps_tools_and_skipped_nodes():
    from app.modules.workflow.builder.testing import format_test_result

    draft = WorkflowDraft()
    draft.add_node("chatInputNode", "Start")
    draft.add_node("routerNode", "Urgent?", {"first_value": "{{session.message}}", "second_value": "urgent"},
                   connect_from="n1")
    draft.add_node("agentNode", "Urgent Agent", connect_from="n2.output_true", system_prompt="x")
    draft.add_node("chatOutputNode", "Urgent Reply", connect_from="n3")
    draft.add_node("templateNode", "Normal", {"template": "ok"}, connect_from="n2.output_false")
    draft.add_node("chatOutputNode", "Normal Reply", connect_from="n5")
    ids = {draft.alias(n["id"]): n["id"] for n in draft.nodes}

    response = {
        "status": "success",
        "output": {"message": "On it."},
        "failed_nodes": [{"node_id": ids["n3"]}],
        "tool_events": [{"tool_name": "create_ticket", "arguments": {"subject": "x"}, "status": "failed",
                         "error": "no credentials", "result": None}],
        "state": {"nodeExecutionStatus": {
            ids["n1"]: {"type": "chatInputNode", "name": "Start", "status": "success", "time_taken": 2,
                        "output": {"message": "it is urgent"}},
            ids["n2"]: {"type": "routerNode", "name": "Urgent?", "status": "success", "time_taken": 1,
                        "output": {"route": "true"}},
            ids["n3"]: {"type": "agentNode", "name": "Urgent Agent", "status": "failed", "time_taken": 1500,
                        "error": "provider not found"},
        }},
    }
    text = format_test_result(draft, "it is urgent", response)
    assert "Response: On it." in text
    assert 'n3 agentNode "Urgent Agent": FAILED after 1.5s — provider not found' in text
    assert "create_ticket(" in text and "no credentials" in text
    assert 'n5 "Normal"' in text and 'n4 "Urgent Reply"' in text  # reported as not run
    assert ids["n3"] not in text  # only aliases, never raw ids


def test_test_run_refuses_invalid_workflows_and_empty_messages():
    from app.modules.workflow.builder.testing import run_draft_test

    draft = WorkflowDraft()
    draft.add_node("chatInputNode", "Start")
    assert "cannot run until these errors are fixed" in asyncio.run(run_draft_test(draft, "hi"))
    assert "message is required" in asyncio.run(run_draft_test(chatbot(), "  "))


def test_test_run_executes_the_draft_on_the_real_engine():
    """No LLM involved: Start -> template -> reply runs end to end and leaves the draft untouched."""
    from app.modules.workflow.builder.testing import run_draft_test

    draft = WorkflowDraft()
    draft.add_node("chatInputNode", "Start")
    draft.add_node("templateNode", "Echo", {"template": "You said: {{session.message}}"}, connect_from="n1")
    draft.add_node("chatOutputNode", "Reply", connect_from="n2")
    before = json.dumps(draft.to_dict())

    text = asyncio.run(run_draft_test(draft, "hello there"))

    assert "You said: hello there" in text
    assert 'n2 templateNode "Echo": success' in text
    assert "No node failed" in text
    assert json.dumps(draft.to_dict()) == before


# ── Lessons from real builder conversations ───────────────────────────────

STARTER_CANVAS = {
    "nodes": [
        {"id": "start", "type": "chatInputNode", "position": {"x": 0, "y": 0},
         "data": {**catalog.default_data("chatInputNode")}},
        {"id": "tpl", "type": "templateNode", "position": {"x": 300, "y": 0},
         "data": {**catalog.default_data("templateNode")}},
        {"id": "finish", "type": "chatOutputNode", "position": {"x": 600, "y": 0},
         "data": {**catalog.default_data("chatOutputNode"), "name": "Finish"}},
    ],
    "edges": [make_edge("start", "tpl", "output", "input"), make_edge("tpl", "finish", "output", "input")],
}


def test_starter_template_is_cleared_so_a_simple_build_is_one_call():
    """
    Case 1 built beside the starter nodes; a later run spent three model calls discovering and
    removing them. The placeholders are now gone before the builder looks.
    """
    draft = WorkflowDraft.from_canvas(STARTER_CANVAS["nodes"], STARTER_CANVAS["edges"])
    assert [n["type"] for n in draft.nodes] == ["chatInputNode", "chatOutputNode"]
    assert not draft.edges and not draft.baseline_keys
    assert "new, empty agent" in draft.render_outline()
    # Clearing alone is not a change: a turn that only answers a question leaves the canvas as it was.
    assert draft.revision == 0
    assert draft.changes == [{"op": "remove_node", "summary": "Removed Text Template", "node_ids": ["tpl"]}]

    built = draft.add_node("agentNode", "Notes Agent", connect_from="n1", connect_to="n2", system_prompt="Help.")
    assert built["alias"] == "n3"
    assert draft.open_problems() == "No open errors."
    assert "new, empty agent" not in draft.render_outline()
    finalize(draft)
    assert [c["op"] for c in draft.changes] == ["remove_node", "add_node"]


def test_a_configured_canvas_is_not_a_starter_template():
    canvas = chatbot().to_canvas()
    assert not WorkflowDraft.from_canvas(canvas["nodes"], canvas["edges"]).is_starter_template()


def test_instructions_in_an_agents_user_prompt_are_rejected():
    """Case 1: the builder 'fixed' behaviour by stuffing instructions into userPrompt."""
    draft = chatbot()
    draft.set_field(
        "n2", "userPrompt",
        "Search '{{session.message}}' in the Northstar Support — Test KB and include policy IDs. "
        "Clearly inform the user if the information isn't available in the KB.",
    )
    assert "instructions_in_user_prompt" in codes(draft.issues(), "error")
    draft.set_field("n2", "userPrompt", "{{session.message}}")
    assert not codes(draft.issues(), "error")


def test_tool_plumbing_cannot_be_edited_but_parameters_can():
    """Case 1: the builder edited a tool's forwardTemplate when the agent was not calling the tool."""
    draft = chatbot()
    tool = draft.add_tool("n2", "knowledgeBaseNode", "Search", "Search the docs.")["tool"]
    with pytest.raises(DraftError, match="must not be edited directly"):
        draft.update_node(tool, {"forwardTemplate": '{"source.query": "{{session.message}}"}'})
    with pytest.raises(DraftError, match="must not be edited directly"):
        draft.set_field(tool, "forwardTemplate", "{}")

    result = draft.set_field(tool, "parameters", '{"question": "What to look up", "language": "Reply language"}')
    data = draft.find(tool)["data"]
    assert set(data["inputSchema"]) == {"question", "language"}
    assert json.loads(data["forwardTemplate"]) == {
        "source.question": "{{direct_input.parameters.question}}",
        "source.language": "{{direct_input.parameters.language}}",
    }
    assert "parameters" in result["message"] and "forwardTemplate" not in result["message"]


def test_placeholders_bare_variables_and_incomplete_filters_are_errors():
    """Case 2: example code left in a node, {{total_count}} in a template, a filter with no value."""
    draft = WorkflowDraft()
    draft.add_node("chatInputNode", "Start")
    draft.add_node("pythonCodeNode", "Process", connect_from="n1")  # keeps the example code
    draft.add_node("filterNode", "Open Only", {"field": "{{source.completed}}"}, connect_from="n2")
    draft.add_node("templateNode", "Summary", {"template": "You have {{total_count}} tasks"}, connect_from="n3")
    draft.add_node("chatOutputNode", "Reply", connect_from="n4")

    found = {(i.code, i.field) for i in draft.issues() if i.severity == "error"}
    assert ("placeholder_config", "code") in found
    assert ("missing_required_config", "value") in found
    assert ("unknown_variable", "template") in found
    # The example code's own {{parameter1}} is not reported on top of the placeholder error.
    assert ("unknown_variable", "code") not in found


def test_unconditional_fan_out_is_an_error_unless_merged():
    draft = chatbot()
    draft.add_node("templateNode", "Also", {"template": "hi"})
    edge = make_edge(draft.find("n1")["id"], draft.find("n4")["id"], "output", "input")
    draft.edges.append(edge)
    draft.add_node("chatOutputNode", "Second Reply", connect_from="n4")
    assert "parallel_branches" in codes(draft.issues(), "error")


def test_resources_are_listed_only_for_signed_in_canvas_drafts(monkeypatch):
    from app.modules.workflow.builder import tools

    store = {}

    async def fake_load(thread_id):
        return store.get(thread_id)

    async def fake_describe(kind):
        return f"listed {kind}"

    monkeypatch.setattr(tools, "load_draft", fake_load)
    monkeypatch.setattr(tools, "describe_resources", fake_describe)

    store["onboarding"] = chatbot()  # built in the pre-login chat
    canvas = chatbot().to_canvas()
    store["canvas"] = WorkflowDraft.from_canvas(canvas["nodes"], canvas["edges"])

    async def scenario():
        assert "signed in" in await tools.run_tool("onboarding", "list_resources", {"kind": "knowledge_bases"})
        assert "signed in" in await tools.run_tool("nobody", "list_resources", {"kind": "knowledge_bases"})
        assert await tools.run_tool("canvas", "list_resources", {"kind": "knowledge_bases"}) == "listed knowledge_bases"

    asyncio.run(scenario())
    restored = WorkflowDraft.from_dict(json.loads(json.dumps(store["canvas"].to_dict())))
    assert restored.authenticated is True


def test_test_result_calls_out_an_agent_that_ignored_its_tools():
    """Case 1: tools_used was empty, which is why the knowledge base was never consulted."""
    from app.modules.workflow.builder.testing import format_test_result

    draft = chatbot()
    draft.add_tool("n2", "knowledgeBaseNode", "Search Docs", "Search the docs.")
    agent_id = draft.find("n2")["id"]
    status = {agent_id: {"type": "agentNode", "name": "Assistant", "status": "success", "output": {"message": "x"}}}

    silent = format_test_result(draft, "How much is Pro?", {"output": {"message": "x"}, "tool_events": [],
                                                           "state": {"nodeExecutionStatus": status}})
    assert "answered without calling any of its tools (Search Docs)" in silent

    used = format_test_result(draft, "How much is Pro?", {
        "output": {"message": "x"}, "state": {"nodeExecutionStatus": status},
        "tool_events": [{"agent_id": agent_id, "tool_name": "search_docs", "status": "succeeded", "result": "r"}],
    })
    assert "answered without calling" not in used


def test_exact_logic_shape_runs_on_the_real_engine():
    """
    The exact_logic recipe without its API call: a Python check, a router on its result,
    and a reply that reads the earlier result by node id after the router.
    """
    from app.modules.workflow.builder.testing import run_draft_test

    draft = WorkflowDraft()
    draft.add_node("chatInputNode", "Start")
    draft.add_node("pythonCodeNode", "Read User Id", {"code": (
        "def executable_function(params):\n"
        "    text = str(params.get(\"session.message\") or \"\")\n"
        "    digits = \"\".join(ch for ch in text if ch.isdigit())\n"
        "    return {\"valid\": \"yes\" if digits else \"no\", \"user_id\": digits}\n"
    )}, connect_from="n1")
    draft.add_node("routerNode", "Valid Id?", {
        "first_value": "{{source.result.valid}}", "compare_condition": "equal", "second_value": "yes",
    }, connect_from="n2")
    draft.add_node("templateNode", "Found", {"template": "Looking up user {{node_outputs.n2.result.user_id}}"},
                   connect_from="n3.output_true")
    draft.add_node("chatOutputNode", "Found Reply", connect_from="n4")
    draft.add_node("templateNode", "Invalid Id", {"template": "That is not a valid user id."},
                   connect_from="n3.output_false")
    draft.add_node("chatOutputNode", "Invalid Reply", connect_from="n6")
    assert not codes(draft.issues(), "error")

    valid = asyncio.run(run_draft_test(draft, "my id is 42"))
    assert "Response: Looking up user 42" in valid
    assert 'n6 "Invalid Id"' in valid.split("Did not run")[1]

    invalid = asyncio.run(run_draft_test(draft, "no idea"))
    assert "Response: That is not a valid user id." in invalid
    assert 'n4 "Found"' in invalid.split("Did not run")[1]


def test_recipes_only_use_valid_variables():
    from app.modules.workflow.builder.patterns import PATTERNS
    from app.modules.workflow.builder.validation import VARIABLE_ROOTS, _TEMPLATE_REF

    for name, pattern in PATTERNS.items():
        text = json.dumps(pattern.get("plan") or []) + pattern.get("notes", "")
        for root, _rest in _TEMPLATE_REF.findall(text):
            assert root in VARIABLE_ROOTS or root == "total", f"{name}: {{{{{root}}}}}"


# ── Lessons from cases 3 and 4 ────────────────────────────────────────────


def test_finalize_requires_a_test_run_after_behavioural_changes():
    """Case 3: the builder declared the workflow done without ever running it."""
    draft = chatbot()
    with pytest.raises(DraftError, match="test_workflow"):
        draft.finalize()
    draft.needs_test = False
    draft.finalize()

    draft.update_node("n2", name="Renamed")  # a rename cannot change behaviour
    draft.finalize()
    draft.set_field("n2", "systemPrompt", "Be brief.")
    with pytest.raises(DraftError, match="test_workflow"):
        draft.finalize()


def test_a_test_run_through_the_tools_unlocks_finalize(monkeypatch):
    from app.modules.workflow.builder import tools

    store = {}

    async def fake_load(thread_id):
        return WorkflowDraft.from_dict(json.loads(store[thread_id])) if thread_id in store else None

    async def fake_save(thread_id, draft):
        store[thread_id] = json.dumps(draft.to_dict())

    monkeypatch.setattr(tools, "load_draft", fake_load)
    monkeypatch.setattr(tools, "save_draft", fake_save)

    async def scenario():
        run = lambda tool, **args: tools.run_tool("t", tool, args)
        plan = lambda *ops: json.dumps(list(ops))
        added = await run("apply_plan", operations=plan({"op": "add_node", "node_type": "chatInputNode", "name": "Start"}))
        assert "Open errors" in added  # every change reports what is still missing
        await run("apply_plan", operations=plan({"op": "add_node", "node_type": "templateNode", "name": "Echo",
                                                 "connect_from": "n1", "config": {"template": "You said: {{session.message}}"}}))
        done = await run("apply_plan", operations=plan({"op": "add_node", "node_type": "chatOutputNode", "name": "Reply", "connect_from": "n2"}))
        assert done.endswith("No open errors.")
        assert "test_workflow" in await run("finalize_workflow")
        assert "You said: hi" in await run("test_workflow", message="hi")
        assert (await run("finalize_workflow")).startswith("Workflow finalized")

    asyncio.run(scenario())


def test_adding_a_node_without_a_connection_says_so():
    """Case 4: an agent and a switch were added but Start was never connected to anything."""
    draft = WorkflowDraft()
    draft.add_node("chatInputNode", "Start")
    loose = draft.add_node("agentNode", "Support Agent", system_prompt="Help.")
    assert "NOT CONNECTED YET" in loose["message"]
    wired = draft.add_node("chatOutputNode", "Reply", connect_from="n2")
    assert "NOT CONNECTED YET" not in wired["message"]
    assert "dead_end" in draft.open_problems() or "no_output_node" in draft.open_problems()
    draft.connect("n1", "n2")
    assert draft.open_problems() == "No open errors."


def test_python_code_is_unescaped_checked_and_must_define_the_entry_function():
    """Case 3: code stored as one line of literal \\n crashed with a syntax error at run time."""
    draft = WorkflowDraft()
    draft.add_node("chatInputNode", "Start")
    escaped = 'def executable_function(params):\\n    text = params.get(\\"session.message\\")\\n    return {\\"ok\\": text}\\n'
    draft.add_node("pythonCodeNode", "Check", {"code": escaped}, connect_from="n1")
    code = draft.find("n2")["data"]["code"]
    assert code.count("\n") == 3 and "\\n" not in code and 'params.get("session.message")' in code

    with pytest.raises(DraftError, match="not valid Python"):
        draft.set_field("n2", "code", "def executable_function(params):\n    return {")
    with pytest.raises(DraftError, match="executable_function"):
        draft.set_field("n2", "code", "def run(params):\n    return 1\n")
    assert draft.find("n2")["data"]["code"] == code  # rejected writes change nothing


def test_test_result_flags_errors_that_nodes_return_as_output():
    """Case 3: the Python node 'succeeded' while its output was a syntax error."""
    from app.modules.workflow.builder.testing import format_test_result

    draft = WorkflowDraft()
    draft.add_node("chatInputNode", "Start")
    draft.add_node("pythonCodeNode", "Check", {"code": "def executable_function(params):\n    return 1\n"},
                   connect_from="n1")
    node_id = draft.find("n2")["id"]
    text = format_test_result(draft, "{}", {
        "has_failures": False, "failed_nodes": [], "output": {"error": "Syntax error: bad"},
        "state": {"nodeExecutionStatus": {node_id: {
            "type": "pythonCodeNode", "name": "Check", "status": "success",
            "output": {"error": "Syntax error: bad", "output": ""}}}},
    })
    assert 'n2 pythonCodeNode "Check": ERROR' in text and "Syntax error: bad" in text
    assert "CODE ERROR: n2 raised an error" in text
    assert "Response: none" in text and "No node failed" not in text


def test_the_persons_canvas_test_run_reaches_the_builder_condensed(monkeypatch):
    """They should not have to paste a 100 KB debug log into the chat."""
    from app.modules.workflow.builder import tools

    canvas = chatbot().to_canvas()
    agent_id = next(n["id"] for n in canvas["nodes"] if n["type"] == "agentNode")
    run = {
        "inputs": {"message": "How much is Pro?"},
        "response": {
            "output": {"message": "I cannot help with that."},
            "tool_events": [],
            "state": {"nodeExecutionStatus": {agent_id: {
                "type": "agentNode", "name": "Assistant", "status": "success",
                "output": {"message": "I cannot help with that.", "padding": "x" * 200_000}}}},
        },
    }
    draft = WorkflowDraft.from_canvas(canvas["nodes"], canvas["edges"], last_test_run=run)
    assert "by the person on the canvas — input: How much is Pro?" in draft.last_user_test
    assert "I cannot help with that." in draft.last_user_test
    assert len(draft.last_user_test) < 3000
    assert "get_last_test_run" in draft.render_outline()

    async def fake_load(thread_id):
        return draft

    monkeypatch.setattr(tools, "load_draft", fake_load)
    assert "How much is Pro?" in asyncio.run(tools.run_tool("t", "get_last_test_run", {}))

    untested = WorkflowDraft.from_canvas(canvas["nodes"], canvas["edges"])
    assert "get_last_test_run" not in untested.render_outline()


# ── Lessons from the meeting-notes run (29 model calls, same IndexError 11 times) ──

BRITTLE_PARSER = (
    "import json\n\n\n"
    "def executable_function(params):\n"
    "    text = str(params.get(\"session.message\") or \"\").strip()\n"
    "    summary = \"\"\n"
    "    for line in text.splitlines():\n"
    "        if \"summary:\" in line.lower():\n"
    "            summary = line.split(\"summary:\", 1)[1].strip()\n"
    "    return {\"output\": json.dumps({\"summary\": summary})}\n"
)


def brittle_draft() -> WorkflowDraft:
    draft = WorkflowDraft()
    draft.add_node("chatInputNode", "Start")
    draft.add_node("pythonCodeNode", "Extract", {"code": BRITTLE_PARSER}, connect_from="n1")
    draft.add_node("chatOutputNode", "Result", connect_from="n2")
    return draft


def test_a_crashing_code_step_is_reported_with_its_line_not_as_success():
    """The builder was shown raw JSON and 'No node failed', so it rewrote the code blind 11 times."""
    from app.modules.workflow.builder.testing import (
        error_signature, run_draft_test, test_found_code_error, test_was_attempted,
    )

    text = asyncio.run(run_draft_test(brittle_draft(), "Summary: on track. Decision: launch."))

    assert "IndexError: list index out of range" in text
    assert 'at line 9 of its code: `summary = line.split("summary:", 1)[1].strip()`' in text
    assert "Response: none" in text and "No node failed" not in text
    assert "language model step" in text
    assert 'n3 chatOutputNode "Result": received the error above' in text
    assert test_was_attempted(text) and test_found_code_error(text)
    assert error_signature(text) and "0." not in error_signature(text).split("ERROR")[1][:6]


def test_a_failing_test_does_not_unlock_finalize_and_repeats_are_stopped(monkeypatch):
    from app.modules.workflow.builder import tools

    store = {"t": json.dumps(brittle_draft().to_dict())}

    async def fake_load(thread_id):
        return WorkflowDraft.from_dict(json.loads(store[thread_id])) if thread_id in store else None

    async def fake_save(thread_id, draft):
        store[thread_id] = json.dumps(draft.to_dict())

    monkeypatch.setattr(tools, "load_draft", fake_load)
    monkeypatch.setattr(tools, "save_draft", fake_save)

    async def scenario():
        run = lambda tool, **args: tools.run_tool("t", tool, args)
        message = "Summary: on track."
        first = await run("test_workflow", message=message)
        assert "STOP AND RETHINK" not in first
        # A run that crashed is not the workflow's test.
        assert "test_workflow" in await run("finalize_workflow")
        await run("test_workflow", message=message)
        third = await run("test_workflow", message=message)
        assert "STOP AND RETHINK: this is the same failure 3 times" in third
        await run("test_workflow", message=message)
        await run("test_workflow", message=message)
        sixth = await run("test_workflow", message=message)
        assert sixth.startswith("STOP: 5 test runs in a row have failed")

        # A real fix clears the counters and unlocks finalize.
        fixed = BRITTLE_PARSER.replace('line.split("summary:", 1)[1]', 'line.lower().split("summary:", 1)[1]')
        await run("set_node_field", node_id="n2", field="code", value=fixed)
        store["t"] = json.dumps({**json.loads(store["t"]), "failed_tests": 0})  # a new turn resets the cap
        assert "No node failed" in await run("test_workflow", message=message)
        assert (await run("finalize_workflow")).startswith("Workflow finalized")

    asyncio.run(scenario())


def test_guidance_sends_free_text_understanding_to_a_language_model():
    from app.db.seed.knowledge.generate_workflow_builder_workflow import build_system_prompt
    from app.modules.workflow.builder.patterns import PATTERNS, describe

    prompt = build_system_prompt()
    assert "does the input have to be understood" in prompt
    assert "text_transform" in prompt
    recipe = describe("text_transform")
    assert '"node_type": "llmModelNode"' in recipe and "pythonCodeNode" in recipe
    assert "Not for understanding free text" in PATTERNS["exact_logic"]["summary"]


# ── Phase 1: fewer model calls ────────────────────────────────────────────


def test_apply_plan_builds_a_whole_workflow_with_temporary_ids():
    from app.modules.workflow.builder.tools import apply_plan

    draft = WorkflowDraft()
    draft.add_node("chatInputNode", "Start")
    draft.add_node("chatOutputNode", "Reply")
    plan = [
        {"op": "add_node", "id": "$agent", "node_type": "agentNode", "name": "Support",
         "system_prompt": "Help.", "connect_from": "n1", "connect_to": "n2"},
        {"op": "add_tool", "id": "$docs", "agent_id": "$agent", "node_type": "knowledgeBaseNode",
         "name": "Search Docs", "description": "Search.", "config": {"selectedBases": ["kb-1"]}},
        {"op": "add_node", "id": "$fmt", "node_type": "templateNode", "name": "Format",
         "config": {"template": "{{node_outputs.$agent.message}} ({{node_outputs.$docs.node.result}})"},
         "connect_from": "$agent", "connect_to": "n2"},
        {"op": "set_node_field", "node_id": "$agent", "field": "maxIterations", "value": "9"},
    ]
    text = apply_plan(draft, json.dumps(plan))
    assert text.startswith("Applied 4 of 4 operations.")
    agent, template = draft.find("Support"), draft.find("Format")
    assert agent["data"]["maxIterations"] == 9 and not agent["data"].get("providerId")
    # Temporary ids became real ids inside config, and the tool's wrapped node is addressable as $docs.node.
    assert agent["id"] in template["data"]["template"]
    assert "$" not in template["data"]["template"]
    assert not codes(draft.issues(), "error")
    assert {(draft.alias(e["source"]), draft.alias(e["target"])) for e in draft.edges if is_main(e)} == {
        ("n1", "n3"), ("n3", "n6"), ("n6", "n2")
    }


def is_main(edge):
    from app.modules.workflow.builder.validation import is_main_edge
    return is_main_edge(edge)


def test_apply_plan_skips_failed_operations_and_reports_them():
    from app.modules.workflow.builder.tools import apply_plan

    draft = chatbot()
    text = apply_plan(draft, [
        {"op": "add_node", "id": "$x", "node_type": "noSuchNode", "name": "X"},
        {"op": "connect", "source": "$x", "target": "n3"},
        {"op": "add_node", "id": "$t", "node_type": "templateNode", "name": "T", "config": {"template": "hi"},
         "connect_from": "n2", "connect_to": "n3"},
        {"op": "frobnicate"},
    ])
    assert "Applied 1 of 4 operations. 3 failed" in text
    assert "1. add_node ($x) FAILED: Unknown node type 'noSuchNode'" in text
    assert "2. connect FAILED: unknown reference $x" in text
    assert "4. frobnicate FAILED: unknown op" in text
    assert draft.find("T")["type"] == "templateNode"
    with pytest.raises(DraftError, match="JSON array"):
        apply_plan(draft, "{not json")
    bad_id = apply_plan(draft, [{"op": "add_node", "id": "agent", "node_type": "templateNode", "name": "T"}])
    assert 'FAILED: id must look like "$name"' in bad_id


def test_every_recipe_plan_applies_cleanly():
    """The recipes are what the builder copies; a recipe that fails to build teaches it a mistake."""
    from app.modules.workflow.builder.patterns import PATTERNS
    from app.modules.workflow.builder.tools import apply_plan

    for name, pattern in PATTERNS.items():
        if not pattern.get("plan"):
            continue
        if pattern["base"] == "empty":
            draft = WorkflowDraft()
            draft.add_node("chatInputNode", "Start")
            draft.add_node("chatOutputNode", "Reply")
        else:
            draft = WorkflowDraft()  # n1 Start, n2 output, n3 agent: the ids the recipes assume
            draft.add_node("chatInputNode", "Start")
            draft.add_node("chatOutputNode", "Reply")
            draft.add_node("agentNode", "Assistant", system_prompt="Help.", connect_from="n1", connect_to="n2")
        text = apply_plan(draft, pattern["plan"])
        assert "FAILED" not in text, f"{name}: {text}"
        errors = [draft.describe_issue(i) for i in draft.issues() if i.severity == "error"]
        assert not errors, f"{name}: {errors}"
        assert "$" not in json.dumps([n["data"] for n in draft.nodes]), f"{name}: unresolved temporary id"


def test_recipes_render_as_apply_plan_calls():
    from app.modules.workflow.builder.patterns import describe

    text = describe("support_assistant")
    assert "apply_plan(operations=[" in text and '"id": "$agent"' in text
    assert "Replace every <placeholder>" in text
    assert "apply_plan" not in describe("agent_prompt")


def test_get_workflow_includes_workspace_resources_when_signed_in(monkeypatch):
    from app.modules.workflow.builder import tools

    store = {}

    async def fake_load(thread_id):
        return store.get(thread_id)

    async def fake_summary():
        return "Workspace resources:\n- knowledge bases: Northstar KB [text] id=kb-1"

    monkeypatch.setattr(tools, "load_draft", fake_load)
    monkeypatch.setattr(tools.resources, "summary", fake_summary)
    store["anon"] = chatbot()
    canvas = chatbot().to_canvas()
    store["canvas"] = WorkflowDraft.from_canvas(canvas["nodes"], canvas["edges"])

    async def scenario():
        assert "Northstar KB" not in await tools.run_tool("anon", "get_workflow", {})
        assert "Northstar KB [text] id=kb-1" in await tools.run_tool("canvas", "get_workflow", {})

    asyncio.run(scenario())


def test_test_workflow_finalizes_in_the_same_call_when_it_passes(monkeypatch):
    from app.modules.workflow.builder import tools

    draft = WorkflowDraft()
    draft.add_node("chatInputNode", "Start")
    draft.add_node("templateNode", "Echo", {"template": "You said: {{session.message}}"}, connect_from="n1")
    draft.add_node("chatOutputNode", "Reply", connect_from="n2")
    store = {"t": json.dumps(draft.to_dict())}

    async def fake_load(thread_id):
        return WorkflowDraft.from_dict(json.loads(store[thread_id])) if thread_id in store else None

    async def fake_save(thread_id, draft):
        store[thread_id] = json.dumps(draft.to_dict())

    monkeypatch.setattr(tools, "load_draft", fake_load)
    monkeypatch.setattr(tools, "save_draft", fake_save)

    async def scenario():
        run = lambda tool, **args: tools.run_tool("t", tool, args)
        text = await run("test_workflow", message="hi", finalize_if_ok="true", summary="Echo bot")
        assert "You said: hi" in text and "Workflow finalized" in text
        assert WorkflowDraft.from_dict(json.loads(store["t"])).status == STATUS_READY
        # A failing run never finalizes.
        store["t"] = json.dumps(brittle_draft().to_dict())
        failing = await run("test_workflow", message="Summary: x", finalize_if_ok="true")
        assert "CODE ERROR" in failing and "Workflow finalized" not in failing
        assert WorkflowDraft.from_dict(json.loads(store["t"])).status != STATUS_READY

    asyncio.run(scenario())


def test_report_quotes_tool_errors_and_states_setup_completeness():
    """The Northstar run blamed an unselected knowledge base that was in fact selected."""
    from app.modules.workflow.builder.testing import format_test_result

    draft = chatbot()
    draft.add_tool("n2", "knowledgeBaseNode", "Search Docs", "Search.", config={"selectedBases": ["kb-1"]})
    draft.apply_defaults({"providerId": "p1"})
    agent_id = draft.find("n2")["id"]
    response = {
        "output": {"message": "I could not look that up."},
        "tool_events": [{"agent_id": agent_id, "tool_name": "search_docs", "arguments": {"query": "Basic plan"},
                         "status": "failed", "error": "Error processing knowledge tool: vector store unavailable",
                         "result": None}],
        "state": {"nodeExecutionStatus": {agent_id: {"type": "agentNode", "name": "Assistant", "status": "success",
                                                      "output": {"message": "I could not look that up."}}}},
    }
    text = format_test_result(draft, "What is in the Basic plan?", response)
    assert 'search_docs({"query": "Basic plan"}) FAILED. The tool\'s own error: "Error processing knowledge tool: vector store unavailable"' in text
    assert "Report the quoted error to the person as it is" in text
    assert "Setup: every provider, knowledge base and credential field is filled in" in text

    bare = chatbot()
    bare.add_tool("n2", "knowledgeBaseNode", "Search Docs", "Search.")
    assert "Setup still missing on the canvas:" in format_test_result(bare, "x", {"output": {}, "state": {}})


def test_prompt_describes_the_three_call_turn():
    from app.db.seed.knowledge.generate_workflow_builder_workflow import build_system_prompt

    prompt = build_system_prompt()
    assert "A normal turn is three calls: apply_plan, test_workflow with finalize_if_ok, then your reply" in prompt
    # The outline arrives with the message; the agent is not told to fetch it first.
    assert "Start every turn with get_workflow" not in prompt
    assert "Every message arrives with the current workflow outline" in prompt
    assert "Repeat that error to the person as it is" in prompt


def test_turn_context_is_the_outline_framed_for_the_message(monkeypatch):
    from app.modules.workflow.builder import tools

    draft = chatbot()

    async def fake_load(thread_id):
        return draft if thread_id == "canvas" else None

    monkeypatch.setattr(tools, "load_draft", fake_load)

    async def scenario():
        context = await tools.turn_context("canvas")
        assert context.startswith(tools.TURN_CONTEXT_HEADER + "\n")
        assert context.endswith("\n\n" + tools.TURN_CONTEXT_FOOTER)
        # The same outline get_workflow returns, so the two never disagree.
        assert await tools.workflow_outline("canvas") in context
        assert await tools.run_tool("canvas", "get_workflow", {}) == await tools.workflow_outline("canvas")
        # No draft yet: the agent is told the workflow is empty, not handed an error.
        assert "WORKFLOW (empty)" in await tools.turn_context("nobody")

    asyncio.run(scenario())
    assert "arrives with it" in next(t for t in tools.TOOL_DEFINITIONS if t["name"] == "get_workflow")["description"]


def test_builder_tools_node_hands_the_outline_to_the_agent_each_turn(monkeypatch):
    from app.modules.workflow.builder import tools
    from app.modules.workflow.engine.nodes import WorkflowBuilderToolsNode

    seen = []

    async def fake_turn_context(thread_id):
        seen.append(thread_id)
        return "OUTLINE"

    monkeypatch.setattr("app.modules.workflow.engine.nodes.workflow_builder_tools_node.turn_context", fake_turn_context)
    node = WorkflowBuilderToolsNode("tools", {"data": {"name": "Workflow Builder Tools"}}, _State())

    assert asyncio.run(node.turn_context()) == "OUTLINE"
    assert seen == ["thread-1"]


# ── Focused AI actions (assist) ───────────────────────────────────────────


def test_assist_actions_build_focused_context_and_proposals(monkeypatch):
    from app.modules.workflow.builder import assist

    asked = []

    async def fake_ask(system, user, provider_id=None):
        asked.append((system, user))
        if "Reply with a JSON array of strings only" in user:
            return '["How much is Pro?", "I want a refund", "What is the weather?"]'
        if "Reply with a JSON array of" in user:
            return json.dumps([{"title": "Add a topic gate", "why": "Rule is only in the prompt",
                                "operations": [{"op": "set_node_field", "node_id": "n2", "field": "maxIterations", "value": "5"}]}])
        if "Reply with the new prompt only" in user:
            return "```\nYou are the support assistant of Acme. We help customers...\n```"
        if "Reply with the code only" in user:
            return "def executable_function(params):\n    return {\"ok\": True}\n"
        return "This step answers customer questions."

    monkeypatch.setattr(assist, "_ask", fake_ask)
    draft = chatbot()
    draft.add_tool("n2", "knowledgeBaseNode", "Search Docs", "Search the docs.", config={"selectedBases": ["kb"]})
    draft.add_node("pythonCodeNode", "Count", connect_from="n2")
    agent_id, code_id = draft.find("n2")["id"], draft.find("Count")["id"]

    async def scenario():
        text = await assist.run_action(draft, "explain_node", [agent_id])
        assert text == {"kind": "text", "text": "This step answers customer questions."}
        assert "n2 agentNode" in asked[-1][1] and "Nodes:" in asked[-1][1]

        prompt = await assist.run_action(draft, "improve_prompt", [agent_id], "make it friendlier")
        op = prompt["proposals"][0]["operations"][0]
        assert op == {"op": "set_node_field", "node_id": "n2", "field": "systemPrompt",
                      "value": "You are the support assistant of Acme. We help customers..."}
        assert "Search the docs." in asked[-1][1] and "make it friendlier" in asked[-1][1]

        code = await assist.run_action(draft, "generate_code", [code_id], "count the words")
        assert code["proposals"][0]["operations"][0]["field"] == "code"
        assert "executable_function" in code["proposals"][0]["operations"][0]["value"]

        tests = await assist.run_action(draft, "suggest_tests", [])
        assert tests == {"kind": "messages", "messages": ["How much is Pro?", "I want a refund", "What is the weather?"]}

        better = await assist.run_action(draft, "optimize", [])
        assert better["proposals"][0]["title"] == "Add a topic gate"
        assert "A step that nothing leads into" not in asked[-1][1]  # focused context, not the builder prompt

        with pytest.raises(ValueError, match="no system prompt"):
            await assist.run_action(draft, "improve_prompt", [code_id])
        with pytest.raises(ValueError, match="Unknown action"):
            await assist.run_action(draft, "dance", [])

    asyncio.run(scenario())


def test_generated_code_is_syntax_checked(monkeypatch):
    from app.modules.workflow.builder import assist

    async def fake_ask(system, user, provider_id=None):
        return "def executable_function(params):\n    return {"

    monkeypatch.setattr(assist, "_ask", fake_ask)
    draft = chatbot()
    draft.add_node("pythonCodeNode", "Count", connect_from="n2")
    with pytest.raises(DraftError, match="not valid Python"):
        asyncio.run(assist.run_action(draft, "generate_code", [draft.find("Count")["id"]], "count"))


def test_review_finds_prompt_leaks_and_structural_gaps():
    from app.modules.workflow.builder.assist import review

    draft = chatbot()
    draft.set_field("n2", "systemPrompt", "If the answer is not in the knowledge base, say so clearly.")
    draft.add_node("switchNode", "Route", {"switchValue": "{{session.message}}", "cases": [{"label": "a", "value": "a"}]})
    findings = review(draft)
    codes_found = {f["code"] for f in findings}
    assert {"prompt_leak", "thin_prompt", "switch_no_default", "unreachable_node"} <= codes_found
    leak = next(f for f in findings if f["code"] == "prompt_leak")
    assert leak["node_id"] == draft.find("n2")["id"] and leak["fix"].startswith("Rewrite the system prompt")
    assert findings[0]["severity"] == "error"  # errors first


def test_proposals_apply_through_apply_plan_on_a_canvas_snapshot():
    from app.modules.workflow.builder.tools import apply_plan

    canvas = chatbot().to_canvas()
    draft = WorkflowDraft.from_canvas(canvas["nodes"], canvas["edges"])
    report = apply_plan(draft, [{"op": "set_node_field", "node_id": "n2", "field": "systemPrompt", "value": "A proper brief."}])
    assert report.startswith("Applied 1 of 1")
    payload = draft.client_payload()
    assert payload["changes"][0]["op"] == "update_node"
    assert next(n for n in payload["nodes"] if n["type"] == "agentNode")["data"]["systemPrompt"] == "A proper brief."


def test_builder_tests_simulate_action_nodes_unless_turned_off():
    from app.modules.workflow.builder.testing import run_draft_test

    draft = WorkflowDraft()
    draft.add_node("chatInputNode", "Start")
    draft.add_node("slackMessageNode", "Notify", {"message": "New: {{session.message}}", "channel": "#x"}, connect_from="n1")
    draft.add_node("templateNode", "Done", {"template": "Sent."}, connect_from="n2")
    draft.add_node("chatOutputNode", "Reply", connect_from="n3")

    text = asyncio.run(run_draft_test(draft, "hello"))
    assert "Response: Sent." in text
    assert 'Simulated (nothing was really sent or created): n2 "Notify"' in text
    assert not draft.find("n2")["data"].get("deactivated")  # the draft itself is untouched

    draft.simulate_actions = False
    real = asyncio.run(run_draft_test(draft, "hello"))
    assert "Simulated" not in real


def test_dangling_connections_from_the_canvas_are_dropped_not_reported():
    """A canvas edge to a deleted node left the builder with an error it had no action for."""
    canvas = chatbot().to_canvas()
    canvas["edges"].append(make_edge(canvas["nodes"][0]["id"], "ghost-node", "output", "input"))
    draft = WorkflowDraft.from_canvas(canvas["nodes"], canvas["edges"])
    assert len(draft.edges) == 2
    assert "edge_unknown_node" not in codes(draft.issues())


def test_search_web_tool_returns_compact_results(monkeypatch):
    """The builder's web search is a handful of title/link/snippet lines, never the node's full envelope."""
    from app.core.utils import web_search_guard, web_search_utils
    from app.modules.workflow.builder import tools

    captured = {}

    async def fake_search(query, *, max_results, **_):
        captured["query"], captured["max_results"] = query, max_results
        return [
            web_search_utils.SearchResult("Acme pricing", "https://acme.test/pricing", "Plans   from  $9 " + "x" * 400, "acme.test", 1),
            web_search_utils.SearchResult("Acme docs", "https://acme.test/docs", "", "acme.test", 2),
        ]

    async def allow(_tenant):
        return True

    monkeypatch.setattr(web_search_utils, "search_web", fake_search)
    monkeypatch.setattr(web_search_guard, "check_enabled", lambda: True)
    monkeypatch.setattr(web_search_guard, "check_tenant_rate", allow)

    result = asyncio.run(tools.run_tool("t", "search_web", {"query": "  acme pricing "}))
    assert captured == {"query": "acme pricing", "max_results": tools.SEARCH_RESULTS}
    assert result.startswith("1. Acme pricing\n   https://acme.test/pricing\n   Plans from $9")
    assert "…" in result and len(result) < 600  # whitespace collapsed, snippet truncated
    assert result.endswith("2. Acme docs\n   https://acme.test/docs")
    assert "search_web" in tools.TOOL_NAMES and "search_web" in tools._READ_ONLY


def test_search_web_tool_respects_guards_and_never_raises(monkeypatch):
    from app.core.utils import web_search_guard, web_search_utils
    from app.modules.workflow.builder import tools

    async def allow(_tenant):
        return True

    async def deny(_tenant):
        return False

    async def boom(query, **_):
        raise web_search_utils.WebSearchError("Search query exceeds 400 characters", category="invalid_config")

    async def network_down(query, **_):
        raise RuntimeError("connect to https://duckduckgo.com failed")

    async def nothing(query, **_):
        return []

    monkeypatch.setattr(web_search_guard, "check_tenant_rate", allow)
    monkeypatch.setattr(web_search_guard, "check_enabled", lambda: False)
    assert "disabled" in asyncio.run(tools.run_tool("t", "search_web", {"query": "x"}))

    monkeypatch.setattr(web_search_guard, "check_enabled", lambda: True)
    monkeypatch.setattr(web_search_guard, "check_tenant_rate", deny)
    assert "rate limit" in asyncio.run(tools.run_tool("t", "search_web", {"query": "x"}))

    monkeypatch.setattr(web_search_guard, "check_tenant_rate", allow)
    assert asyncio.run(tools.run_tool("t", "search_web", {})) == "query is required."

    monkeypatch.setattr(web_search_utils, "search_web", boom)
    out = asyncio.run(tools.run_tool("t", "search_web", {"query": "x"}))
    assert out.startswith("Web search failed: Search query exceeds 400 characters") and "Do not retry" in out

    monkeypatch.setattr(web_search_utils, "search_web", network_down)
    out = asyncio.run(tools.run_tool("t", "search_web", {"query": "x"}))
    assert "unavailable" in out and "duckduckgo" not in out

    monkeypatch.setattr(web_search_utils, "search_web", nothing)
    assert 'No results for "x"' in asyncio.run(tools.run_tool("t", "search_web", {"query": "x"}))


def test_backend_starter_workflow_is_recognised_and_cleared():
    """A brand-new agent's canvas (Start -> Text Template -> Finish, from the backend default) is a starter."""
    from app.schemas.workflow import get_base_workflow

    base = get_base_workflow("My Agent")
    draft = WorkflowDraft.from_canvas(base.nodes, base.edges)
    assert draft.starter_cleared is True
    assert sorted(draft.aliases.values()) == ["n1", "n2"]
    # The first thing the builder does on a starter canvas must just work.
    draft.add_node("agentNode", "Coordinator Agent", None, "n1", "n2", "You coordinate.")
    assert not [i for i in draft.issues() if i.severity == "error"]

    # The same template, edited by the person, is their work and is kept.
    edited = json.loads(json.dumps(base.nodes))
    next(n for n in edited if n["type"] == "templateNode")["data"]["template"] = "Reply in French: {{source.message}}"
    kept = WorkflowDraft.from_canvas(edited, base.edges)
    assert kept.starter_cleared is False and len(kept.aliases) == 3


def test_knowledge_base_id_aliases_become_selected_bases():
    draft = chatbot()
    draft.add_tool("n2", "knowledgeBaseNode", "Docs", "Search the docs.", config={"knowledgeBaseId": "kb-1"})
    kb = next(n for n in draft.nodes if n["type"] == "knowledgeBaseNode")
    assert kb["data"]["selectedBases"] == ["kb-1"]
    draft.add_tool("n2", "knowledgeBaseNode", "More", "More docs.", config={"knowledge_bases": ["a", "b"], "selectedBases": ["a"]})
    kb2 = [n for n in draft.nodes if n["type"] == "knowledgeBaseNode"][-1]
    assert kb2["data"]["selectedBases"] == ["a", "b"]
    with pytest.raises(DraftError, match="lookup_node"):
        draft.add_tool("n2", "knowledgeBaseNode", "Bad", "x", config={"collection": "y"})


def test_bare_placeholders_in_a_tool_config_become_declared_parameters():
    """The agent wrote {{city_name}} in an API tool's settings: that is a tool parameter, not an unknown variable."""
    draft = chatbot()
    result = draft.add_tool(
        "n2", "apiToolNode", "Geocode", "Resolve a city to coordinates.",
        config={"endpoint": "https://geo.test/search", "method": "GET", "parameters": {"name": "{{city_name}}", "count": "1"}},
    )
    tool = next(n for n in draft.nodes if n["type"] == "toolBuilderNode")
    api = next(n for n in draft.nodes if n["type"] == "apiToolNode")
    assert api["data"]["parameters"] == {"name": "{{source.city_name}}", "count": "1"}
    assert list(tool["data"]["inputSchema"]) == ["city_name"]
    assert "city_name" in result["message"] and "declared" in result["message"]
    assert not [i for i in draft.issues() if i.code == "unknown_variable"]

    # Declared parameters and proper variables are left alone.
    draft.add_tool(
        "n2", "apiToolNode", "Weather", "Current weather.",
        config={"endpoint": "https://w.test", "parameters": {"lat": "{{latitude}}", "lon": "{{parameters.longitude}}", "msg": "{{source.message}}"}},
        parameters={"latitude": "Latitude."},
    )
    api2 = [n for n in draft.nodes if n["type"] == "apiToolNode"][-1]
    assert api2["data"]["parameters"] == {"lat": "{{source.latitude}}", "lon": "{{source.longitude}}", "msg": "{{source.message}}"}
    tool2 = [n for n in draft.nodes if n["type"] == "toolBuilderNode"][-1]
    assert list(tool2["data"]["inputSchema"]) == ["latitude", "longitude"]


# ── Narration, questions, add_step ────────────────────────────────────────


def test_tool_calls_are_narrated_as_steps_on_a_streamed_turn(monkeypatch):
    """Each builder tool call becomes a start/end step frame in plain words, named after the step it touches."""
    import contextvars

    from app.core import turn_stream
    from app.modules.workflow.builder import tools

    draft = WorkflowDraft()
    draft.add_node("chatInputNode", "Start")
    draft.add_node("agentNode", "Support Agent", {"systemPrompt": "Help."}, connect_from="n1")
    store = {"t": json.dumps(draft.to_dict())}

    async def fake_load(thread_id):
        return WorkflowDraft.from_dict(json.loads(store[thread_id])) if thread_id in store else None

    async def fake_save(thread_id, draft):
        store[thread_id] = json.dumps(draft.to_dict())

    monkeypatch.setattr(tools, "load_draft", fake_load)
    monkeypatch.setattr(tools, "save_draft", fake_save)

    async def scenario():
        stream = turn_stream.TurnStream("conv")
        turn_stream.current_stream.set(stream)
        await tools.run_tool("t", "get_node", {"node_id": "n2"})
        await tools.run_tool("t", "apply_plan", {"operations": json.dumps([
            {"op": "add_node", "id": "$out", "node_type": "chatOutputNode", "name": "Reply", "connect_from": "n2"},
        ])})
        await tools.run_tool("t", "set_node_field", {"node_id": "n2", "field": "systemPrompt", "value": "Help politely."})
        frames = []
        while not stream.queue.empty():
            frames.append(stream.queue.get_nowait())
        return frames

    frames = contextvars.copy_context().run(lambda: asyncio.run(scenario()))
    events = [json.loads(f.split("data: ", 1)[1]) for f in frames if f.startswith("event: step")]
    texts = [(e["phase"], e["text"], e["detail"]) for e in events]
    assert texts == [
        ("start", "Reading “Support Agent”", ""),
        ("end", "Reading “Support Agent”", ""),
        ("start", "Adding “Reply”", ""),
        ("end", "Adding “Reply”", "1 of 1 applied"),
        ("start", "Writing the prompt of “Support Agent”", ""),
        ("end", "Writing the prompt of “Support Agent”", ""),
    ]
    assert {e["kind"] for e in events} == {"read", "edit"}
    # Outside a streamed turn nothing is emitted and nothing breaks.
    turn_stream.current_stream.set(None)
    assert "Support Agent" in asyncio.run(tools.run_tool("t", "get_node", {"node_id": "n2"}))


def test_narration_describes_plans_and_outcomes():
    from app.modules.workflow.builder import narration

    assert narration.describe_plan(json.dumps([
        {"op": "add_node", "name": "Classifier"}, {"op": "add_node", "name": "Router"},
        {"op": "connect"}, {"op": "set_node_field"},
    ])) == "Adding “Classifier” and “Router”, changing 1 step and connecting them"
    assert narration.describe_plan([{"op": "add_node"}] * 3 + [{"op": "remove_node"}]) == "Adding 3 steps and removing 1 step"
    assert narration.describe_plan("not json") == "Applying changes"
    assert narration.describe_call("test_workflow", {"message": "x" * 100})[1].startswith("Testing with “xxxx")
    assert narration.describe_call("search_web", {"query": "acme pricing"}) == ("search", "Searching the web for “acme pricing”")
    assert narration.describe_outcome("apply_plan", "Applied 5 of 7 operations. 2 failed") == "5 of 7 applied, 2 failed"
    assert narration.describe_outcome("search_web", "1. A\n   url\n2. B\n   url") == "2 results"
    assert narration.describe_outcome("set_node_field", "ERROR: no such field") == "Rejected: no such field"
    assert narration.describe_outcome("finalize_workflow", "Workflow finalized. Tell the user") == "Finalized"


def test_ask_user_records_a_question_the_canvas_shows_as_options(monkeypatch):
    """ask_user stores the question on the draft (no revision change) and tells the agent to stop and ask."""
    from app.modules.workflow.builder import tools

    draft = WorkflowDraft()
    draft.add_node("chatInputNode", "Start")
    store = {"t": json.dumps(draft.to_dict())}
    revision = draft.revision

    async def fake_load(thread_id):
        return WorkflowDraft.from_dict(json.loads(store[thread_id]))

    async def fake_save(thread_id, draft):
        store[thread_id] = json.dumps(draft.to_dict())

    monkeypatch.setattr(tools, "load_draft", fake_load)
    monkeypatch.setattr(tools, "save_draft", fake_save)

    result = asyncio.run(tools.run_tool("t", "ask_user", {
        "question": "  What should happen when nobody is available? ",
        "options": json.dumps(["Email the customer", "Open a ticket", "open a ticket", "Do nothing"]),
        "recommended": "open a Ticket",
    }))
    assert "End your turn now" in result and "Do not list the options" in result
    saved = WorkflowDraft.from_dict(json.loads(store["t"]))
    assert saved.revision == revision
    assert saved.question == {
        "question": "What should happen when nobody is available?",
        "options": ["Email the customer", "Open a ticket", "Do nothing"],
        "recommended": "Open a ticket",
    }
    assert saved.client_payload()["question"] == saved.question
    # The next turn starts from the canvas, which carries no question.
    fresh = WorkflowDraft.from_canvas(saved.nodes, saved.edges, previous=saved)
    assert fresh.question is None and fresh.client_payload()["question"] is None

    assert asyncio.run(tools.run_tool("t", "ask_user", {"question": "Only one?", "options": '["Yes"]'})).startswith("ERROR:")
    assert asyncio.run(tools.run_tool("t", "ask_user", {"question": "", "options": '["a", "b"]'})).startswith("ERROR:")
    # A pipe-separated list is accepted too; an unknown recommendation is simply dropped.
    assert "End your turn" in asyncio.run(tools.run_tool("t", "ask_user", {"question": "Which?", "options": "A | B", "recommended": "C"}))
    assert WorkflowDraft.from_dict(json.loads(store["t"])).question == {"question": "Which?", "options": ["A", "B"], "recommended": None}


def test_add_step_proposes_one_node_connected_from_the_chosen_output(monkeypatch):
    from app.modules.workflow.builder import assist

    asked = []

    async def fake_ask(system, user, provider_id=None):
        asked.append(user)
        if "between" in user:
            return json.dumps({
                "op": "add_node", "node_type": "llmModelNode", "name": "Summarize the request",
                "system_prompt": "Summarize the customer's message in one sentence.", "connect_to": "n3",
                "id": "$ignored", "connect_from": "n9",
            })
        return "```json\n" + json.dumps({"op": "add_node", "node_type": "templateNode", "name": "Thanks", "config": {"template": "Thanks!"}}) + "\n```"

    monkeypatch.setattr(assist, "_ask", fake_ask)

    draft = WorkflowDraft()
    draft.add_node("chatInputNode", "Start")
    draft.add_node("agentNode", "Agent", {"systemPrompt": "Help."}, connect_from="n1")
    draft.add_node("chatOutputNode", "Reply", connect_from="n2")
    agent_id = draft.find("n2")["id"]

    # Between the agent and its reply: the model's connect_to is kept, its own ids are overridden.
    result = asyncio.run(assist.run_action(draft, "add_step", [agent_id], "summarize what the customer asked"))
    assert result["kind"] == "proposals"
    [proposal] = result["proposals"]
    assert proposal["title"] == 'Add "Summarize the request"'
    assert proposal["operations"] == [{
        "op": "add_node", "id": "$new", "node_type": "llmModelNode", "name": "Summarize the request",
        "connect_from": "n2", "system_prompt": "Summarize the customer's message in one sentence.", "connect_to": "n3",
    }]
    assert "currently leads to" in asked[0] and "summarize what the customer asked" in asked[0]
    # Applying it inserts the step between the two.
    from app.modules.workflow.builder.tools import apply_plan

    report = apply_plan(draft, proposal["operations"])
    assert "FAILED" not in report
    new_node = draft.find("Summarize the request")
    assert any(e["source"] == agent_id and e["target"] == new_node["id"] for e in draft.edges)
    assert any(e["source"] == new_node["id"] and e["target"] == draft.find("n3")["id"] for e in draft.edges)
    assert not any(e["source"] == agent_id and e["target"] == draft.find("n3")["id"] for e in draft.edges)

    # A branching node names the output; a bad output is refused; an empty instruction too.
    draft2 = WorkflowDraft()
    draft2.add_node("chatInputNode", "Start")
    draft2.add_node("switchNode", "Router", {
        "switchValue": "{{session.message}}", "cases": [{"id": "case_1", "label": "Billing", "value": "billing"}],
    }, connect_from="n1")
    switch_id = draft2.find("n2")["id"]
    outputs = catalog.handle_ids("switchNode", draft2.find("n2")["data"], "source")
    assert len(outputs) > 1
    result = asyncio.run(assist.run_action(draft2, "add_step", [switch_id], "thank them", source_handle=outputs[-1]))
    assert result["proposals"][0]["operations"][0]["connect_from"] == f"n2.{outputs[-1]}"
    assert "leads nowhere yet" in asked[-1]
    with pytest.raises(ValueError):
        asyncio.run(assist.run_action(draft2, "add_step", [switch_id], "thank them", source_handle="output_nope"))
    with pytest.raises(ValueError):
        asyncio.run(assist.run_action(draft2, "add_step", [switch_id], "   "))


# ── Lessons from the Northstar Support triage run (24 model calls, $0.40) ───────


def test_reading_a_key_the_previous_node_never_outputs_is_an_error():
    """Eight calls went into discovering that an agent's output has no `result`."""
    draft = WorkflowDraft()
    draft.add_node("chatInputNode", "Start")
    draft.add_node("agentNode", "Analyst", {"systemPrompt": "Classify."}, connect_from="n1")
    draft.add_node("pythonCodeNode", "Parse", {"code": (
        "import json\n\ndef executable_function(params):\n"
        "    raw = params.get(\"source.result\") or params.get(\"source.data\") or \"\"\n"
        "    return json.loads(raw)\n"
    )}, connect_from="n2")
    draft.add_node("templateNode", "Reply", {"template": "{{source.result.category}} / {{node_outputs.n2.result}}"},
                   connect_from="n3")
    draft.add_node("chatOutputNode", "Out", connect_from="n4")

    mismatches = [i for i in draft.issues() if i.code == "source_shape_mismatch"]
    assert {(i.node_id, i.field) for i in mismatches} == {(draft.find("n3")["id"], "code"), (draft.find("n4")["id"], "template")}
    code_issue = next(i for i in mismatches if i.field == "code")
    assert "source.result" in code_issue.message and "outputs {message, steps, tools_used}" in code_issue.message
    assert 'params.get("source.message")' in code_issue.message
    # The template after the Python step reads source.result correctly; only node_outputs.n2.result is wrong.
    template_issue = draft.describe_issue(next(i for i in mismatches if i.field == "template"))
    assert "node_outputs.n2.result" in template_issue and "source.result" not in template_issue
    assert "source_shape_mismatch" in draft.open_problems()

    # The right paths are quiet.
    draft.set_field("n3", "code", (
        "import json\n\ndef executable_function(params):\n"
        "    try:\n        return json.loads(params.get(\"source.message\") or \"\")\n"
        "    except Exception:\n        return {\"category\": \"general\"}\n"
    ))
    draft.set_field("n4", "template", "{{source.result.category}} / {{node_outputs.n2.message}}")
    assert not [i for i in draft.issues() if i.code == "source_shape_mismatch"]

    # An unknown upstream shape (an API step) and an unwrapped Python step are not judged.
    draft.update_node("n3", {"unwrap": True})
    draft.set_field("n4", "template", "{{source.anything}}")
    assert not [i for i in draft.issues() if i.code == "source_shape_mismatch"]


def test_the_catalog_tells_the_builder_what_an_agent_outputs():
    text = catalog.node_schema_text("pythonCodeNode")
    assert 'params.get("source.message")' in text and '"steps"' in text and "json.loads" in text
    assert 'params.get("source.data")' not in text.split("after an apiToolNode")[0].split("Which path exists")[0]
    assert "{{source.message}}" in catalog.node_schema_text("agentNode")
    from app.modules.workflow.builder import patterns

    assert 'params.get("source.message") after an agent' in patterns.describe("variables")


def test_an_agent_whose_reply_feeds_a_parser_is_created_without_memory():
    from app.modules.workflow.builder.tools import apply_plan

    draft = WorkflowDraft()
    draft.add_node("chatInputNode", "Start")
    report = apply_plan(draft, [
        {"op": "add_node", "id": "$analyst", "node_type": "agentNode", "name": "Analyst",
         "system_prompt": "Classify the message.", "connect_from": "n1"},
        {"op": "add_node", "id": "$parse", "node_type": "pythonCodeNode", "name": "Parse",
         "config": {"code": "def executable_function(params):\n    return {\"c\": params.get(\"source.message\")}\n"},
         "connect_from": "$analyst"},
        {"op": "add_node", "id": "$helper", "node_type": "agentNode", "name": "Helper",
         "system_prompt": "Help the customer.", "connect_from": "$parse"},
        {"op": "add_node", "id": "$out", "node_type": "chatOutputNode", "name": "Reply", "connect_from": "$helper"},
        {"op": "add_node", "id": "$chosen", "node_type": "agentNode", "name": "Chosen",
         "system_prompt": "Classify, but remember.", "config": {"memory": True}},
        {"op": "add_node", "id": "$sw", "node_type": "switchNode", "name": "Route",
         "config": {"switchValue": "{{source.message}}", "cases": [{"label": "A", "value": "a"}]},
         "connect_from": "$chosen"},
    ])

    assert "FAILED" not in report
    assert draft.find("Analyst")["data"]["memory"] is False  # its reply is parsed by code
    assert draft.find("Helper")["data"]["memory"] is True  # it talks to the person
    assert draft.find("Chosen")["data"]["memory"] is True  # the builder said so explicitly
    assert "Memory turned off on n2:" in report and "parses or compares" in report


def test_a_change_and_a_test_sent_in_the_same_step_test_the_changed_workflow(monkeypatch):
    """The agent loop runs one step's tool calls concurrently; the test must not read the draft
    before a change sent with it has landed (two identical tests disagreed in the triage run)."""
    from app.modules.workflow.builder import tools

    draft = WorkflowDraft()
    draft.add_node("chatInputNode", "Start")
    draft.add_node("templateNode", "Echo", {"template": "You said: {{session.message}}"}, connect_from="n1")
    draft.add_node("chatOutputNode", "Reply", connect_from="n2")
    store = {"t": json.dumps(draft.to_dict())}

    async def fake_load(thread_id):
        await asyncio.sleep(0.01)  # a round trip to the store
        return WorkflowDraft.from_dict(json.loads(store[thread_id])) if thread_id in store else None

    async def fake_save(thread_id, draft):
        await asyncio.sleep(0.02)  # the write takes longer than the test's read would
        store[thread_id] = json.dumps(draft.to_dict())

    monkeypatch.setattr(tools, "load_draft", fake_load)
    monkeypatch.setattr(tools, "save_draft", fake_save)

    async def one_step():
        return await asyncio.gather(
            tools.run_tool("t", "set_node_field", {"node_id": "n2", "field": "template", "value": "Echo: {{session.message}}"}),
            tools.run_tool("t", "test_workflow", {"message": "hi"}),
        )

    written, tested = asyncio.run(one_step())
    assert written.startswith("Updated n2: template.")
    assert "Echo: hi" in tested and "You said" not in tested
    assert "changed while this test was running" not in tested
    assert WorkflowDraft.from_dict(json.loads(store["t"])).needs_test is False


def test_a_test_report_made_stale_by_a_concurrent_change_says_so(monkeypatch):
    from app.modules.workflow.builder import tools

    store = {"t": json.dumps(chatbot().to_dict())}

    async def fake_load(thread_id):
        return WorkflowDraft.from_dict(json.loads(store[thread_id]))

    async def fake_save(thread_id, draft):
        store[thread_id] = json.dumps(draft.to_dict())

    async def run_while_changing(draft, message, usage_sink=None, simulate_actions=None):
        # A write lands after the test started (a call the model sent after the test in the same step).
        await tools.run_tool("t", "set_node_field", {"node_id": "n2", "field": "systemPrompt", "value": "Be brief."})
        return "TEST RUN — input: hi\nResponse: ok\nExecution (in order):\n- n2 agentNode \"Assistant\": success in 0.1s → ok\nNo node failed."

    monkeypatch.setattr(tools, "load_draft", fake_load)
    monkeypatch.setattr(tools, "save_draft", fake_save)
    monkeypatch.setattr(tools, "run_draft_test", run_while_changing)

    result = asyncio.run(tools.run_tool("t", "test_workflow", {"message": "hi", "finalize_if_ok": "true"}))

    assert "NOTE: the workflow changed while this test was running" in result
    assert "Workflow finalized" not in result
    latest = WorkflowDraft.from_dict(json.loads(store["t"]))
    assert latest.needs_test is True  # the changed version is still untested


def test_repeated_outputs_are_quoted_once_in_a_test_report():
    """The same knowledge base passage was quoted three times per report (tool node, wrapper, tool call)."""
    from app.modules.workflow.builder.testing import format_test_result

    draft = chatbot()
    agent_id = draft.find("n2")["id"]
    tool = draft.add_tool("n2", "knowledgeBaseNode", "Search Docs", "Search the docs.", {"selectedBases": ["kb-1"]})
    kb_id, wrapper_id = draft.find(tool["node"])["id"], draft.find(tool["tool"])["id"]
    passage = {"results": [{"text": "Precedence: incidents outrank billing; billing outranks sales. " + "More rules. " * 20}]}
    short = {"ok": True}
    text = format_test_result(draft, "hi", {
        "output": {"message": "done"}, "failed_nodes": [],
        "tool_events": [{"agent_id": agent_id, "tool_name": "Search Docs", "arguments": {"q": "precedence"},
                         "status": "success", "result": passage}],
        "state": {"nodeExecutionStatus": {
            kb_id: {"type": "knowledgeBaseNode", "name": "Search Docs", "status": "success", "output": passage},
            wrapper_id: {"type": "toolBuilderNode", "name": "Search Docs", "status": "success", "output": passage},
            agent_id: {"type": "agentNode", "name": "Assistant", "status": "success", "output": short},
            draft.find("n3")["id"]: {"type": "chatOutputNode", "name": "Reply", "status": "success", "output": short},
        }},
    })

    assert text.count("Precedence: incidents outrank billing") == 1
    assert text.count("(same output as ") == 2
    assert text.count('{"ok": true}') == 2  # short outputs are always shown in full


def test_test_run_usage_is_tagged_so_the_builders_own_cost_stays_apart(monkeypatch):
    from types import SimpleNamespace

    from app.modules.workflow.builder.testing import run_draft_test
    from app.modules.workflow.engine.workflow_engine import WorkflowEngine
    from app.modules.workflow.engine.workflow_state import BUILDER_TEST_RUN_PURPOSE

    async def fake_execute(self, input_data, thread_id, persist, usage_sink):
        usage_sink.append({"input_tokens": 10, "output_tokens": 2, "provider": "openai", "model": "gpt-4o", "purpose": None})
        usage_sink.append({"input_tokens": 1, "output_tokens": 1, "provider": "openai", "model": "gpt-4o", "purpose": "compaction"})
        return SimpleNamespace(format_state_as_response=lambda: {
            "output": {"message": "hi"}, "failed_nodes": [], "state": {"nodeExecutionStatus": {}},
        })

    monkeypatch.setattr(WorkflowEngine, "execute_from_node", fake_execute)
    draft = WorkflowDraft()  # no AI step, so no provider is needed to start the run
    draft.add_node("chatInputNode", "Start")
    draft.add_node("templateNode", "Echo", {"template": "{{session.message}}"}, connect_from="n1")
    draft.add_node("chatOutputNode", "Reply", connect_from="n2")
    sink: list = []
    report = asyncio.run(run_draft_test(draft, "hello", usage_sink=sink))

    assert "Response: hi" in report
    assert [u["purpose"] for u in sink] == [BUILDER_TEST_RUN_PURPOSE, "compaction"]


def test_the_agent_loop_narrates_parallel_tool_calls_into_the_turn_stream(monkeypatch):
    """The thinking trail is fed by the step frames run_tool emits. The real agent loop runs the
    calls of one step concurrently and through the new middleware; every call must still narrate."""
    import contextvars
    from types import SimpleNamespace

    from langchain_core.language_models import BaseChatModel
    from langchain_core.messages import AIMessage
    from langchain_core.outputs import ChatGeneration, ChatResult

    from app.core import turn_stream
    from app.modules.workflow.agents.react_agent_lc import ReActAgentLC
    from app.modules.workflow.builder import tools
    from app.modules.workflow.engine.nodes.workflow_builder_tools_node import WorkflowBuilderToolsNode

    store = {"t": json.dumps(chatbot().to_dict())}

    async def fake_load(thread_id):
        return WorkflowDraft.from_dict(json.loads(store[thread_id])) if thread_id in store else None

    async def fake_save(thread_id, draft):
        store[thread_id] = json.dumps(draft.to_dict())

    monkeypatch.setattr(tools, "load_draft", fake_load)
    monkeypatch.setattr(tools, "save_draft", fake_save)

    class Scripted(BaseChatModel):
        replies: list = []
        calls: int = 0

        @property
        def _llm_type(self) -> str:
            return "scripted"

        def bind_tools(self, tools, **kwargs):
            return self

        def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
            self.calls += 1
            return ChatResult(generations=[ChatGeneration(message=self.replies[self.calls - 1])])

        async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
            return self._generate(messages, stop, run_manager, **kwargs)

    model = Scripted(replies=[
        AIMessage(content="", tool_calls=[
            {"name": "get_workflow", "args": {}, "id": "c1", "type": "tool_call"},
            {"name": "lookup_node", "args": {"query": "pythonCodeNode"}, "id": "c2", "type": "tool_call"},
        ]),
        AIMessage(content="Done."),
    ])
    state = SimpleNamespace(
        get_thread_id=lambda: "t", llm_usage=[], workflow={"nodes": [], "edges": []}, target_edges={},
        set_node_input=lambda *a, **k: None, initial_values={},
    )
    node = WorkflowBuilderToolsNode("tools", {"type": "workflowBuilderToolsNode", "data": {}}, state)

    async def scenario():
        stream = turn_stream.TurnStream("conv")
        turn_stream.current_stream.set(stream)
        agent = ReActAgentLC(llm_model=model, system_prompt="sys", tools=node.get_tools(), max_iterations=5)
        result = await agent.invoke("hi")
        frames = []
        while not stream.queue.empty():
            frames.append(stream.queue.get_nowait())
        return result, frames

    result, frames = contextvars.copy_context().run(lambda: asyncio.run(scenario()))

    assert result["status"] == "success" and result["response"] == "Done."
    events = [json.loads(f.split("data: ", 1)[1]) for f in frames if f.startswith("event: step")]
    assert sorted((e["phase"], e["text"]) for e in events) == sorted([
        ("start", "Reading the workflow"), ("end", "Reading the workflow"),
        ("start", "Looking up “pythonCodeNode”"), ("end", "Looking up “pythonCodeNode”"),
    ])
    assert [t["tool_name"] for t in result["tools_used"]] == ["get_workflow", "lookup_node"]


def test_seeded_builder_runs_on_its_own_default_provider():
    """The builder's agent node points at the provider seed.py creates for it, not the analysts' one"""
    import json
    from pathlib import Path

    from app.db.seed.knowledge.generate_workflow_builder_workflow import OUTPUT_PATH
    from app.db.seed.seed_data_config import seed_test_data

    seeded = json.loads(Path(OUTPUT_PATH).read_text())
    agents = [n for n in seeded["nodes"] if n["type"] == "agentNode"]
    assert [n["data"]["providerId"] for n in agents] == [seed_test_data.workflow_builder_llm_provider_id]
    assert seed_test_data.workflow_builder_llm_provider_id != seed_test_data.llm_provider_id


@pytest.mark.asyncio
async def test_the_tools_route_lists_every_builder_tool_by_name_and_description():
    from app.api.v1.routes.workflow_builder import list_builder_tools
    from app.modules.workflow.builder.tools import TOOL_DEFINITIONS

    listed = await list_builder_tools()

    assert [t["name"] for t in listed] == [d["name"] for d in TOOL_DEFINITIONS]
    assert all(set(t) == {"name", "description"} and t["description"] for t in listed)
