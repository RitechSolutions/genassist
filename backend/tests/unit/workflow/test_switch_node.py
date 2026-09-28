"""Tests for SwitchNode.process().

Covers: each match mode, case sensitivity, first-match-wins ordering, the default
branch (no match, missing value, unsupported mode, broken regex), exact handle
matching so ``case_1`` never follows ``case_10`` edges, and non-string values.
"""

from types import SimpleNamespace

import pytest

from app.modules.workflow.engine.nodes.switch_node import SwitchNode

CASES = [
    {"id": "case_1", "label": "Billing", "value": "billing"},
    {"id": "case_2", "label": "Sales", "value": "sales"},
    {"id": "case_10", "label": "Cancellation", "value": "cancel"},
]

EDGES = [
    {"source": "sw", "target": "billing_agent", "sourceHandle": "output_case_1"},
    {"source": "sw", "target": "sales_agent", "sourceHandle": "output_case_2"},
    {"source": "sw", "target": "cancel_agent", "sourceHandle": "output_case_10"},
    {"source": "sw", "target": "fallback", "sourceHandle": "output_default"},
]


def _make_node(edges=None):
    state = SimpleNamespace(source_edges={"sw": EDGES if edges is None else edges})
    config = {"type": "switchNode", "data": {"name": "Switch"}}
    return SwitchNode("sw", config, state)


async def _route(value, **config):
    return await _make_node().process({"switchValue": value, "cases": CASES, **config})


@pytest.mark.asyncio
async def test_equal_match_routes_to_case_branch_only():
    result = await _route("billing")
    assert result["route"] == "case_1"
    assert result["label"] == "Billing"
    assert result["matched_case"] == CASES[0]
    assert result["next_nodes"] == ["billing_agent"]


@pytest.mark.asyncio
async def test_case_handle_is_matched_exactly_not_by_prefix():
    # output_case_1 is a prefix of output_case_10; only case_1's edge may run.
    result = await _route("billing")
    assert "cancel_agent" not in result["next_nodes"]

    result = await _route("cancel")
    assert result["route"] == "case_10"
    assert result["next_nodes"] == ["cancel_agent"]


@pytest.mark.asyncio
async def test_no_match_routes_to_default():
    result = await _route("shipping")
    assert result["route"] == "default"
    assert result["label"] == "Default"
    assert result["matched_case"] is None
    assert result["next_nodes"] == ["fallback"]


@pytest.mark.asyncio
async def test_matching_is_case_insensitive_and_trims_by_default():
    result = await _route("  BILLING\n")
    assert result["route"] == "case_1"
    assert result["value"] == "BILLING"


@pytest.mark.asyncio
async def test_case_sensitive_requires_exact_case():
    assert (await _route("Billing", caseSensitive=True))["route"] == "default"
    assert (await _route("billing", caseSensitive="true"))["route"] == "case_1"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mode, value, expected",
    [
        ("contains", "I have a billing question", "case_1"),
        ("starts_with", "sales lead from web", "case_2"),
        ("ends_with", "please cancel", "case_10"),
        ("regex", "SALES-42", "case_2"),
    ],
)
async def test_match_modes(mode, value, expected):
    cases = CASES if mode != "regex" else [
        {"id": "case_1", "label": "Billing", "value": r"^bill"},
        {"id": "case_2", "label": "Sales", "value": r"^sales-\d+$"},
    ]
    result = await _make_node().process({"switchValue": value, "matchMode": mode, "cases": cases})
    assert result["route"] == expected


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "value, case_value",
    [(3.0, "3"), ("3.0", "3"), ("3", "3.0"), ("2.50", "2.5"), ("1e3", "1000"), (-4.0, "-4")],
)
async def test_equal_matches_the_same_number_written_differently(value, case_value):
    cases = [{"id": "case_1", "label": "Three", "value": case_value}]
    result = await _make_node().process({"switchValue": value, "matchMode": "equal", "cases": cases})
    assert result["route"] == "case_1"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "value, case_value",
    [("007", "7"), ("3.1", "3"), ("12345678901234567891.0", "12345678901234567890"), ("3.0abc", "3")],
)
async def test_equal_keeps_different_numbers_and_digit_ids_apart(value, case_value):
    cases = [{"id": "case_1", "label": "Hit", "value": case_value}]
    result = await _make_node().process({"switchValue": value, "matchMode": "equal", "cases": cases})
    assert result["route"] == "default"


@pytest.mark.asyncio
async def test_number_formatting_is_only_reconciled_for_equal():
    cases = [{"id": "case_1", "label": "Three", "value": "3"}]
    result = await _make_node().process({"switchValue": "3.0", "matchMode": "ends_with", "cases": cases})
    assert result["route"] == "default"


@pytest.mark.asyncio
async def test_first_matching_case_wins():
    cases = [
        {"id": "case_1", "label": "Urgent", "value": "urgent"},
        {"id": "case_2", "label": "Urgent billing", "value": "urgent billing"},
    ]
    edges = [
        {"source": "sw", "target": "a", "sourceHandle": "output_case_1"},
        {"source": "sw", "target": "b", "sourceHandle": "output_case_2"},
    ]
    result = await _make_node(edges).process(
        {"switchValue": "urgent billing issue", "matchMode": "contains", "cases": cases}
    )
    assert result["route"] == "case_1"
    assert result["next_nodes"] == ["a"]


@pytest.mark.asyncio
async def test_invalid_regex_case_is_skipped_not_raised():
    cases = [
        {"id": "case_1", "label": "Broken", "value": "(unclosed"},
        {"id": "case_2", "label": "Sales", "value": "sales"},
    ]
    result = await _make_node().process({"switchValue": "sales", "matchMode": "regex", "cases": cases})
    assert result["route"] == "case_2"


@pytest.mark.asyncio
async def test_missing_value_routes_to_default():
    result = await _make_node().process({"switchValue": "", "cases": CASES})
    assert result["route"] == "default"
    assert result["next_nodes"] == ["fallback"]


@pytest.mark.asyncio
async def test_unsupported_match_mode_routes_to_default():
    result = await _route("billing", matchMode="fuzzy")
    assert result["route"] == "default"


@pytest.mark.asyncio
async def test_empty_case_values_never_match():
    cases = [{"id": "case_1", "label": "Empty", "value": ""}]
    result = await _make_node().process({"switchValue": "anything", "matchMode": "contains", "cases": cases})
    assert result["route"] == "default"


@pytest.mark.asyncio
async def test_malformed_cases_are_ignored():
    cases = [
        "not a dict",
        {"label": "No id", "value": "billing"},
        {"id": "default", "label": "Reserved", "value": "billing"},
        {"id": "case_3", "value": "billing"},
    ]
    result = await _make_node().process({"switchValue": "billing", "cases": cases})
    assert result["route"] == "case_3"
    # A case without a label falls back to its position.
    assert result["label"] == "Case 4"


@pytest.mark.asyncio
async def test_matched_case_without_connected_branch_stops_there():
    result = await _make_node(edges=[]).process({"switchValue": "billing", "cases": CASES})
    assert result["route"] == "case_1"
    assert result["next_nodes"] == []


@pytest.mark.asyncio
@pytest.mark.parametrize("value, case_value", [(42, "42"), (True, "true"), (None, "none")])
async def test_non_string_values_are_compared_as_text(value, case_value):
    cases = [{"id": "case_1", "label": "Hit", "value": case_value}]
    result = await _make_node().process({"switchValue": value, "cases": cases})
    expected = "default" if value is None else "case_1"
    assert result["route"] == expected


# ---- Smart Mode ------------------------------------------------------------


@pytest.fixture
def smart_llm(monkeypatch):
    """Patch the LLM provider so Smart Mode answers with ``smart_llm.answer``."""
    from app.modules.workflow.engine import llm_usage_tracking
    from app.modules.workflow.engine.nodes import switch_node

    fake = SimpleNamespace(answer="case_2", error=None, messages=None, provider_ids=[])

    async def ainvoke(messages):
        if fake.error:
            raise fake.error
        fake.messages = messages
        return SimpleNamespace(content=fake.answer)

    model = SimpleNamespace(bind=lambda **_: SimpleNamespace(ainvoke=ainvoke))

    async def get_model(provider_id):
        fake.provider_ids.append(provider_id)
        return model

    provider = SimpleNamespace(get_model=get_model)
    monkeypatch.setattr(switch_node.injector, "get", lambda _cls: provider)

    async def _no_usage(*_args, **_kwargs):
        return None

    monkeypatch.setattr(llm_usage_tracking, "record_node_llm_usage", _no_usage)
    return fake


def _smart(**overrides):
    return {
        "smartModeEnabled": True,
        "providerId": "p1",
        "smartPrompt": "Route this message: I want to buy more seats",
        "cases": CASES,
        **overrides,
    }


@pytest.mark.asyncio
async def test_smart_mode_routes_to_the_case_the_llm_picks(smart_llm):
    result = await _make_node().process(_smart())
    assert result["route"] == "case_2"
    assert result["smartModeEnabled"] is True
    assert result["next_nodes"] == ["sales_agent"]
    assert smart_llm.provider_ids == ["p1"]


@pytest.mark.asyncio
async def test_smart_mode_prompt_lists_every_case_and_the_default(smart_llm):
    await _make_node().process(_smart())
    system, human = smart_llm.messages
    assert "routing decision engine" in system.content
    assert human.content.startswith("Route this message")
    for line in ("- case_1: Billing - billing", "- case_2: Sales - sales", "- default:"):
        assert line in human.content


@pytest.mark.asyncio
async def test_smart_mode_uses_a_custom_system_prompt(smart_llm):
    await _make_node().process(_smart(systemPrompt="Pick a queue."))
    assert smart_llm.messages[0].content == "Pick a queue."


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "answer, route",
    [("  `CASE_10`.\n", "case_10"), ("Billing", "case_1"), ("default", "default"), ("refunds", "default")],
)
async def test_smart_mode_accepts_ids_or_labels_and_defaults_otherwise(smart_llm, answer, route):
    smart_llm.answer = answer
    assert (await _make_node().process(_smart()))["route"] == route


@pytest.mark.asyncio
@pytest.mark.parametrize("answer", ["default", "Default", " `DEFAULT`. "])
async def test_smart_mode_default_answer_is_reserved_even_with_a_case_labelled_default(smart_llm, answer):
    cases = [
        {"id": "case_1", "label": "Billing", "value": "billing questions"},
        {"id": "case_2", "label": "Default", "value": "a case the user named Default"},
    ]
    edges = [
        {"source": "sw", "target": "labelled_default", "sourceHandle": "output_case_2"},
        {"source": "sw", "target": "fallback", "sourceHandle": "output_default"},
    ]
    smart_llm.answer = answer
    result = await _make_node(edges).process(_smart(cases=cases))
    assert result["route"] == "default"
    assert result["next_nodes"] == ["fallback"]


@pytest.mark.asyncio
async def test_smart_mode_case_labelled_default_is_still_reachable_by_its_id(smart_llm):
    cases = [{"id": "case_2", "label": "Default", "value": "a case the user named Default"}]
    smart_llm.answer = "case_2"
    assert (await _make_node().process(_smart(cases=cases)))["route"] == "case_2"


@pytest.mark.asyncio
async def test_smart_mode_llm_error_routes_to_default(smart_llm):
    smart_llm.error = RuntimeError("provider down")
    result = await _make_node().process(_smart())
    assert result["route"] == "default"
    assert result["next_nodes"] == ["fallback"]


@pytest.mark.asyncio
@pytest.mark.parametrize("missing", ["providerId", "smartPrompt", "cases"])
async def test_smart_mode_missing_config_routes_to_default_without_calling_llm(smart_llm, missing):
    result = await _make_node().process(_smart(**{missing: [] if missing == "cases" else ""}))
    assert result["route"] == "default"
    assert smart_llm.provider_ids == []


@pytest.mark.asyncio
async def test_smart_mode_ignores_the_rule_value(smart_llm):
    # The rule value would match case_1, but Smart Mode decides by LLM.
    result = await _make_node().process(_smart(switchValue="billing"))
    assert result["route"] == "case_2"


# ---- engine ----------------------------------------------------------------


def _engine_workflow():
    return {
        "id": "wf1",
        "config": {"id": "wf1"},
        "nodes": [
            {"id": "in", "type": "chatInputNode", "data": {"name": "Start"}},
            {
                "id": "sw",
                "type": "switchNode",
                "data": {
                    "name": "Intent",
                    "switchValue": "{{session.message}}",
                    "matchMode": "equal",
                    "cases": CASES[:2],
                },
            },
            {"id": "billing", "type": "templateNode", "data": {"name": "B", "template": "billing"}},
            {"id": "sales", "type": "templateNode", "data": {"name": "S", "template": "sales"}},
            {"id": "other", "type": "templateNode", "data": {"name": "D", "template": "default"}},
        ],
        "edges": [
            {"source": "in", "target": "sw", "sourceHandle": "output", "targetHandle": "input"},
            {"source": "sw", "target": "billing", "sourceHandle": "output_case_1", "targetHandle": "input"},
            {"source": "sw", "target": "sales", "sourceHandle": "output_case_2", "targetHandle": "input"},
            {"source": "sw", "target": "other", "sourceHandle": "output_default", "targetHandle": "input"},
        ],
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "message, route, branch",
    [("Sales", "case_2", "sales"), ("billing", "case_1", "billing"), ("shipping", "default", "other")],
)
async def test_engine_runs_only_the_selected_branch(message, route, branch):
    from app.modules.workflow.engine.workflow_engine import WorkflowEngine

    state = await WorkflowEngine(_engine_workflow()).execute_from_node(
        input_data={"message": message}, persist=False
    )
    assert state.node_outputs["sw"]["route"] == route
    ran = {n for n in ("billing", "sales", "other") if n in state.node_outputs}
    assert ran == {branch}


@pytest.mark.asyncio
async def test_duplicate_edges_to_same_target_run_it_once():
    edges = [
        {"source": "sw", "target": "a", "sourceHandle": "output_case_1"},
        {"source": "sw", "target": "a", "sourceHandle": "output_case_1"},
        {"source": "sw", "target": "b", "sourceHandle": "output_case_1"},
    ]
    result = await _make_node(edges).process({"switchValue": "billing", "cases": CASES})
    assert result["next_nodes"] == ["a", "b"]
