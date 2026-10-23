"""Registry must stay in sync with dialogs and engine"""

import re
from pathlib import Path

import pytest

from app.modules.workflow.prompt_fields import (
    LEGACY_BUCKET_FOR_NODE_TYPE,
    LEGACY_SHARED_NODE_IDS,
    PROMPT_FIELDS,
    get_spec,
)
from app.schemas.dynamic_form_schemas.nodes import NODE_DIALOG_SCHEMAS

_ENGINE_SOURCE = Path(__file__).parents[2] / "app/modules/workflow/engine/workflow_engine.py"
_GUARDRAIL_SOURCE = (
    Path(__file__).parents[2] / "app/modules/workflow/engine/nodes/guardrail_provenance_node.py"
)

_REGISTERED_FIELDS = [
    (node_type, field, spec)
    for node_type, fields in PROMPT_FIELDS.items()
    for field, spec in fields.items()
]

_HAND_WRITTEN_DIALOGS = {"guardrailProvenanceNode"}

_SCHEMA_BACKED_FIELDS = [
    entry for entry in _REGISTERED_FIELDS if entry[0] not in _HAND_WRITTEN_DIALOGS
]


def test_the_guardrail_is_the_only_dialog_without_a_dynamic_schema():
    unschemad = {n for n, _, _ in _REGISTERED_FIELDS if n not in NODE_DIALOG_SCHEMAS}

    assert unschemad == _HAND_WRITTEN_DIALOGS


@pytest.mark.parametrize(
    "node_type,field,spec",
    _SCHEMA_BACKED_FIELDS,
    ids=[f"{node_type}.{field}" for node_type, field, _ in _SCHEMA_BACKED_FIELDS],
)
def test_registered_fields_match_their_dialog_schema(node_type, field, spec):
    dialog_field = next(
        (f for f in NODE_DIALOG_SCHEMAS[node_type] if f.name == field), None
    )

    assert dialog_field is not None, f"{node_type} has no dialog field '{field}'"
    assert spec.field == field
    assert spec.label == dialog_field.label


def test_guardrail_judge_suffix_matches_the_node_config_key():
    spec = get_spec("guardrailProvenanceNode", "llm_judge_system_prompt_suffix")

    assert spec is not None
    assert spec.field == "llm_judge_system_prompt_suffix"
    assert spec.label == "Additional judge instructions"
    source = _GUARDRAIL_SOURCE.read_text()
    assert source.count('config.get("llm_judge_system_prompt_suffix"') == 1


def test_every_registered_node_type_is_an_engine_node_type():
    registered_in_engine = set(
        re.findall(r'cls\._node_registry\["(\w+)"\]', _ENGINE_SOURCE.read_text())
    )

    assert registered_in_engine, "the engine registry literals could not be read"
    assert set(PROMPT_FIELDS) <= registered_in_engine


def test_fields_without_the_inline_check_explain_why():
    for node_type, field, spec in _REGISTERED_FIELDS:
        assert spec.inline_check or spec.unsupported_reason, f"{node_type}.{field}"


def test_only_system_role_fields_support_the_inline_check():
    for node_type, field, spec in _REGISTERED_FIELDS:
        assert spec.inline_check == (spec.role == "system"), f"{node_type}.{field}"


def test_legacy_buckets_cover_the_dialogs_that_shared_a_dom_id():
    assert LEGACY_BUCKET_FOR_NODE_TYPE == {
        "agentNode": "agent-config",
        "llmModelNode": "agent-config",
        "subAgentNode": "sub-agent-config",
    }
    assert set(LEGACY_SHARED_NODE_IDS) == {"agent-config", "sub-agent-config"}


def test_unknown_node_types_and_fields_have_no_spec():
    assert get_spec("chatInputNode", "systemPrompt") is None
    assert get_spec("agentNode", "smartPrompt") is None
