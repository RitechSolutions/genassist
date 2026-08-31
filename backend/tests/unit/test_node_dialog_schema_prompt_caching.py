"""The promptCaching dialog field is declared on exactly the cache-aware node types"""

import pytest

from app.schemas.dynamic_form_schemas.nodes import NODE_DIALOG_SCHEMAS

_CACHE_AWARE = ("agentNode", "subAgentNode", "llmModelNode")


def _field(node_type: str):
    return next((f for f in NODE_DIALOG_SCHEMAS[node_type] if f.name == "promptCaching"), None)


@pytest.mark.parametrize("node_type", _CACHE_AWARE)
def test_cache_aware_nodes_declare_an_optional_boolean_defaulting_off(node_type):
    field = _field(node_type)
    assert field is not None
    assert field.type == "boolean"
    assert field.required is False
    assert field.default is False


@pytest.mark.parametrize("node_type", _CACHE_AWARE)
def test_the_label_matches_the_dialog_switch(node_type):
    assert _field(node_type).label == "Enable Prompt Caching"


def test_no_other_node_type_offers_the_toggle():
    others = set(NODE_DIALOG_SCHEMAS) - set(_CACHE_AWARE)
    assert [t for t in others if _field(t) is not None] == []
