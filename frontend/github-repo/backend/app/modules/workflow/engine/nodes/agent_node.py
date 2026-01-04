"""
Agent node implementation using the BaseNode class.
"""

import datetime
from typing import Dict, Any
import logging

from app.modules.workflow.engine.base_node import BaseNode
from app.modules.workflow.llm.provider import LLMProvider
from app.modules.workflow.agents.react_agent import ReActAgent
from app.modules.workflow.agents.react_agent_lc import ReActAgentLC
from app.modules.workflow.agents.simple_tool_agent import SimpleToolAgent
from app.modules.workflow.agents.tool_agent import ToolAgent

logger = logging.getLogger(__name__)


class AgentNode(BaseNode):
    """Agent node that can select and execute tools using the BaseNode approach"""

    async def process(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process an agent node with tool selection and execution.

        Args:
            config: The resolved configuration for the node

        Returns:
            Dictionary with agent response and execution steps
        """
        # Get configuration values (already resolved by BaseNode)
        provider_id: str | None = config.get("providerId", None)
        # ToolSelector, ReActAgent
        agent_type: str = config.get("type", "ToolSelector")
        max_iterations = config.get("maxIterations", 7)
        memory_enabled = config.get("memory", False)

        # Get input data from state (this would typically come from connected nodes)
        # For now, we'll use default values
        system_prompt = config.get(
            "systemPrompt", "You are a helpful assistant.")
        prompt = config.get("userPrompt", "What is the capital of France?")

        # Get tools from connected nodes using the new generic method
        tools = self.get_connected_nodes("tools")

        # Add current time to system prompt
        system_prompt += f" Current time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

        # Set input for tracking
        self.set_node_input({
            "system_prompt": system_prompt,
            "prompt": prompt,
            "tools_reference": tools
        })

        logger.info("Agent type: %s", agent_type)

        try:
            from app.dependencies.injector import injector
            llm_provider = injector.get(LLMProvider)
            llm_model = await llm_provider.get_model(provider_id)
            logger.info("Agent type selected: %s, LLM model: %s",
                        agent_type, llm_model)

            # Create agent based on type
            if agent_type == "ReActAgent":
                agent = ReActAgent(
                    llm_model=llm_model,
                    system_prompt=system_prompt,
                    tools=tools,
                    max_iterations=max_iterations
                )
            elif agent_type == "ReActAgentLC":
                agent = ReActAgentLC(
                    llm_model=llm_model,
                    system_prompt=system_prompt,
                    tools=tools,
                    max_iterations=max_iterations
                )
            elif agent_type == "SimpleToolExecutor":
                agent = SimpleToolAgent(
                    llm_model=llm_model,
                    system_prompt=system_prompt,
                    tools=tools,
                )
            else:
                agent = ToolAgent(
                    llm_model=llm_model,
                    system_prompt=system_prompt,
                    tools=tools,
                    max_iterations=max_iterations
                )

            # Get chat history if memory is enabled
            chat_history = []
            if memory_enabled:
                chat_history = await self.get_memory().get_messages()

            # Invoke the agent
            result = await agent.invoke(prompt, chat_history=chat_history)
            logger.info("Agent result: %s", result)

            # Prepare output
            output = {
                "message": result.get("response", "Something went wrong"),
                "steps": result.get("reasoning_steps", []) if agent_type in ["ReActAgent", "ReActAgentLC"] else result.get("steps", [])
            }

            return output

        except Exception as e:
            logger.error("Error processing agent node: %s", str(e))
            error_message = f"Error: {str(e)}"
            return {"error": error_message}
