import logging
from typing import List, Dict, Any, Optional
from langchain_core.language_models import BaseChatModel
from app.modules.workflow.agents.base_tool import BaseTool
from app.modules.workflow.agents.base_tool_agent import BaseToolAgent
from app.modules.workflow.agents.agent_utils import (
    validate_tool_parameters,
    create_success_response,
    create_error_response,
    parse_json_response,
    create_tool_descriptions,
)
from app.modules.workflow.agents.agent_prompts import (
    create_tool_agent_tools_available_prompt,
    create_tool_agent_tools_query_prompt,
    create_conversation_context,
    create_tool_agent_no_tools_prompt,
    create_tool_agent_no_tools_query_prompt,
)

logger = logging.getLogger(__name__)


class SimpleToolAgent(BaseToolAgent):
    """A simple agent that uses an LLM to select and invoke a tool based on the query and chat history."""

    def __init__(
        self, llm_model: BaseChatModel, system_prompt: str, tools: List[BaseTool]
    ):
        super().__init__(llm_model, system_prompt, tools)

    def _create_prompt(
        self, query: str, chat_history: Optional[List[Dict[str, str]]] = None
    ) -> str:
        tool_descriptions = create_tool_descriptions(self.tools)
        enhanced_prompt = create_tool_agent_tools_available_prompt(
            self.system_prompt, tool_descriptions
        )
        context = create_conversation_context(chat_history or [])
        return create_tool_agent_tools_query_prompt(enhanced_prompt, context, query)

    def _create_no_tools_prompt(
        self, query: str, chat_history: Optional[List[Dict[str, str]]] = None
    ) -> str:
        enhanced_prompt = create_tool_agent_no_tools_prompt(self.system_prompt)
        context = create_conversation_context(chat_history or [])
        return create_tool_agent_no_tools_query_prompt(enhanced_prompt, context, query)

    async def invoke(
        self, query: str, chat_history: Optional[List[Dict[str, str]]] = None, **kwargs
    ) -> Dict[str, Any]:
        if not self.tools:
            return create_error_response("No tools available", self._get_agent_name())
        prompt = self._create_prompt(query, chat_history)
        try:
            response = await self.llm_model.ainvoke(
                [{"role": "user", "content": prompt}]
            )
            response_content = (
                response.content if hasattr(response, "content") else str(response)
            )
            logger.info(f"SimpleToolAgent LLM response: {response_content}")
            parsed = parse_json_response(response_content)
            if not parsed:
                return create_error_response(
                    "LLM did not return a valid response",
                    self._get_agent_name(),
                    llm_response=response_content,
                )
            if parsed.get("action") == "direct_response":
                return create_success_response(
                    parsed.get("response", ""),
                    self._get_agent_name(),
                    no_tool_used=True,
                    llm_reasoning=parsed.get("reasoning", ""),
                )
            if parsed.get("action") != "tool_call":
                return create_error_response(
                    "LLM did not return a valid tool_call action",
                    self._get_agent_name(),
                    llm_response=response_content,
                )
            tool_name = parsed.get("tool_name")
            parameters = parsed.get("parameters", {})
            tool = self.tool_map.get(tool_name)
            if not tool:
                # If tool not found, ask LLM to answer directly (no tools)
                no_tools_prompt = self._create_no_tools_prompt(query, chat_history)
                direct_response = await self.llm_model.ainvoke(
                    [{"role": "user", "content": no_tools_prompt}]
                )
                direct_content = (
                    direct_response.content
                    if hasattr(direct_response, "content")
                    else str(direct_response)
                )
                direct_parsed = parse_json_response(direct_content)
                answer = (
                    direct_parsed.get("response", direct_content)
                    if direct_parsed
                    else direct_content
                )
                return create_success_response(
                    answer,
                    self._get_agent_name(),
                    no_tool_used=True,
                    tool_not_found=tool_name,
                    llm_reasoning=parsed.get("reasoning", ""),
                )
            validated_params = validate_tool_parameters(tool, parameters)
            result = await tool.invoke(**validated_params)
            logger.info(
                f"SimpleToolAgent: Invoked {tool.name} with {validated_params}, result: {result}"
            )

            # Check if tool has return_direct=True
            if hasattr(tool, "return_direct") and tool.return_direct:
                # Return tool result directly without processing
                return create_success_response(
                    str(result),
                    self._get_agent_name(),
                    tool=tool.name,
                    parameters=validated_params,
                    return_direct=True,
                )

            # Normal processing for non-return_direct tools
            if isinstance(result, dict) and "result" in result:
                result = result["result"]
            elif isinstance(result, dict) and "message" in result:
                result = result["message"]
            else:
                result = str(result)
            return create_success_response(
                result,
                self._get_agent_name(),
                tool=tool.name,
                parameters=validated_params,
            )
        except Exception as e:
            logger.error(f"SimpleToolAgent error: {str(e)}")
            return create_error_response(str(e), self._get_agent_name())

    async def stream(
        self, query: str, chat_history: Optional[List[Dict[str, str]]] = None, **kwargs
    ):
        """Stream the agent's tool selection and execution process"""
        try:
            result = await self.invoke(query, chat_history, **kwargs)
            yield result
        except Exception as e:
            logger.error(f"Error streaming {self._get_agent_name()} query: {str(e)}")
            yield create_error_response(str(e), self._get_agent_name())
