"""Tool Builder forward templates must survive agent parameters with line breaks or quotes.

Mirrors what ToolBuilderNode does at runtime: the node config is resolved with
``replace_config_vars`` (direct_input = the agent's tool arguments), then the node parses
``config["forwardTemplate"]`` with ``json.loads``. The template is JSON nested inside the
config JSON, so values need two levels of escaping.
"""

import json

import pytest

from app.modules.workflow.engine.utils import replace_config_vars
from app.modules.workflow.engine.workflow_state import WorkflowState

TICKET_FORWARD_TEMPLATE = (
    '{"source.email":"{{direct_input.parameters.email}}",'
    '"source.reason":"{{direct_input.parameters.reason}}",'
    '"source.subject":"{{direct_input.parameters.subject}}",'
    '"source.description":"{{direct_input.parameters.description}}",'
    '"source.phone_number":"{{direct_input.parameters.phone_number}}",'
    '"source.transaction_id":"{{direct_input.parameters.transaction_id}}"}'
)

ONE_PARAGRAPH = (
    "Charged 16.72 for two hours at location 12345; the posted rate is 3 per hour, "
    "so the correct charge is 6.00. Requesting a refund of the difference."
)

WITH_LINE_BREAKS = (
    "Charged 16.72 for two hours at location 12345. The posted rate is 3 per hour.\n\n"
    "I therefore request:\n"
    "- Reimbursement of the overcharged amount.\n"
    "- Confirmation that the billing error has been corrected.\n"
    "- Clarification of how this discrepancy occurred"
)

WITH_DOUBLE_QUOTES = 'The sign said "3 per hour" but I was charged 16.72.'

WITH_TAB = "Location 12345\tcharged 16.72 instead of 6.00."

WITH_BACKSLASH = "Receipt saved under C:\\parking\\receipt.pdf"


def _resolve_forward_template(description: str) -> str:
    direct_input = {
        "parameters": {
            "email": "customer@example.com",
            "reason": "refund_other",
            "subject": "Refund request for an overcharge",
            "description": description,
            "phone_number": "07000000000",
            "transaction_id": "1700000000000",
        }
    }
    resolved, _ = replace_config_vars(
        config={"forwardTemplate": TICKET_FORWARD_TEMPLATE},
        state=WorkflowState(workflow={"nodes": [], "edges": []}),
        source_output=None,
        direct_input=direct_input,
    )
    return resolved["forwardTemplate"]


class TestToolBuilderForwardTemplateEscaping:
    def test_plain_description_round_trips(self):
        template = json.loads(_resolve_forward_template(ONE_PARAGRAPH))

        assert template["source.description"] == ONE_PARAGRAPH
        assert template["source.email"] == "customer@example.com"

    @pytest.mark.parametrize(
        "description",
        [
            pytest.param(WITH_LINE_BREAKS, id="line-breaks"),
            pytest.param(WITH_DOUBLE_QUOTES, id="double-quotes"),
            pytest.param(WITH_TAB, id="tab"),
            pytest.param(WITH_BACKSLASH, id="backslash"),
        ],
    )
    def test_special_characters_round_trip(self, description):
        template = json.loads(_resolve_forward_template(description))

        assert template["source.description"] == description
        assert template["source.transaction_id"] == "1700000000000"

    def test_other_string_fields_keep_single_escaping(self):
        resolved, _ = replace_config_vars(
            config={"systemPrompt": "Customer said: {{direct_input.text}}"},
            state=WorkflowState(workflow={"nodes": [], "edges": []}),
            source_output=None,
            direct_input={"text": 'line one\nsaid "hi"'},
        )

        assert resolved["systemPrompt"] == 'Customer said: line one\nsaid "hi"'
