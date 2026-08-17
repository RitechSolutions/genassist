"""ToolAgent query prompts stay the system prompt plus a separable portion"""

import pytest

from app.modules.workflow.agents.agent_prompts import (
    create_tool_agent_no_tools_query_portion,
    create_tool_agent_no_tools_query_prompt,
    create_tool_agent_tools_query_portion,
    create_tool_agent_tools_query_prompt,
)

_NO_TOOLS_PORTION = """CTX

User Query: Q

Since no tools are available, provide a direct response based on your knowledge using the JSON format specified above."""

_TOOLS_PORTION = """CTX

User Query: Q

Analyze the query and decide if you need to use any tools. Respond using the JSON format specified above.
- If you need a tool, use the "tool_call" action format
- If you can answer directly, use the "direct_response" action format
- Make sure to include all required parameters and follow the parameter types specified
- Always include your reasoning for the decision"""

_CASES = [
    pytest.param(
        create_tool_agent_no_tools_query_prompt,
        create_tool_agent_no_tools_query_portion,
        _NO_TOOLS_PORTION,
        id="no_tools",
    ),
    pytest.param(
        create_tool_agent_tools_query_prompt,
        create_tool_agent_tools_query_portion,
        _TOOLS_PORTION,
        id="tools",
    ),
]


@pytest.mark.parametrize("fused,portion,expected", _CASES)
class TestQueryPortions:
    def test_portion_renders_verbatim(self, fused, portion, expected):
        assert portion("CTX", "Q") == expected

    def test_fused_prompt_is_the_system_prompt_plus_the_portion(self, fused, portion, expected):
        assert fused("SYS", "CTX", "Q") == "SYS\n\n" + expected

    @pytest.mark.parametrize("system_prompt", ["", "SYS", "multi\nline", "{braces}", "trailing\n\n"], ids=repr)
    def test_portion_carries_no_part_of_the_system_prompt(self, fused, portion, expected, system_prompt):
        assert fused(system_prompt, "CTX", "Q") == system_prompt + "\n\n" + portion("CTX", "Q")
