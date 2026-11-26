"""
Workflow Builder Tools node.

Attaches to an agent's tools handle and gives it the Workflow Builder's tool set
(search nodes, read the draft, add/update/connect/remove nodes, finalize). Like
the MCP node, one canvas node exposes several tools.

The tools act on the workflow draft of the current conversation, so this node
only makes sense inside the Workflow Builder agent's own workflow.
"""

import logging
from typing import Any, Dict, List

from app.modules.workflow.agents.base_tool import BaseTool
from app.modules.workflow.builder.tools import TOOL_DEFINITIONS, make_executor, run_tool, turn_context
from app.modules.workflow.engine.base_node import BaseNode
from app.modules.workflow.engine.node_result import node_failure

logger = logging.getLogger(__name__)

# A plan or a prompt is one long tool argument. Claude returns a tool call that
# outgrew max_tokens with its arguments empty, so the builder needs this much room
# whatever the provider form says (1,024, the old form default, broke every plan).
MIN_MAX_TOKENS = 16000


class WorkflowBuilderToolsNode(BaseNode):
    """Exposes the Workflow Builder tool set to a connected agent."""

    def model_requirements(self) -> Dict[str, Any]:
        """What the connected agent's model needs to drive these tools (see AgentNode)."""
        return {"min_max_tokens": MIN_MAX_TOKENS}

    def get_tools(self) -> List[BaseTool]:
        # An empty selection means "all tools"; the node is useless with none.
        enabled = set(self.get_node_data().get("enabledTools") or [])
        tools: List[BaseTool] = []
        for definition in TOOL_DEFINITIONS:
            if enabled and definition["name"] not in enabled:
                continue
            tools.append(
                BaseTool(
                    node_id=f"{self.node_id}:{definition['name']}",
                    name=definition["name"],
                    description=definition["description"],
                    parameters=definition["parameters"],
                    function=make_executor(
                        self.get_state().get_thread_id,
                        definition["name"],
                        # A test run's LLM usage is accounted to this builder conversation.
                        usage_sink_getter=lambda: getattr(self.get_state(), "llm_usage", None),
                    ),
                )
            )
        return tools

    async def turn_context(self) -> str:
        """The workflow outline, handed to the agent with each message (see AgentNode)."""
        return await turn_context(self.get_state().get_thread_id())

    async def process(self, config: Dict[str, Any]) -> Any:
        """Run one tool directly (node test); in a workflow the agent calls the tools."""
        tool_name = config.get("tool_name")
        if not tool_name:
            return node_failure(
                "This node only provides tools to an agent. Connect it to an agent's tools handle.",
                code=400,
            )
        result = await run_tool(
            self.get_state().get_thread_id(), tool_name, config.get("tool_arguments") or {}
        )
        return {"result": result}
