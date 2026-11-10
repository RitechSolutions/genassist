from typing import TYPE_CHECKING, AsyncIterator, List, Dict, Any, Optional, Union
import logging
import uuid
from langchain_core.language_models import BaseChatModel
from langchain_core.messages.base import BaseMessage
from langchain_core.tools import StructuredTool
from langchain_core.messages import HumanMessage, AIMessage, AIMessageChunk, SystemMessage, ToolMessage
from langchain.agents import create_agent
from langchain.agents.middleware.types import AgentMiddleware, ModelResponse
from langgraph.types import Command
from app.modules.workflow.agents.base_tool import BaseTool
from app.modules.workflow.agents.base_tool_agent import BaseToolAgent
from app.modules.workflow.agents.memory import history_text
from app.core.utils.llm_usage_utils import extract_usage_from_aimessage
from app.modules.workflow.agents.agent_utils import (
    create_error_response,
    create_success_response,
    parse_json_response,
)
import json

if TYPE_CHECKING:
    from app.core.turn_stream import TokenSink

logger = logging.getLogger(__name__)


class RetryOnToolErrorMiddleware(AgentMiddleware):
    """Route failed tool calls back to the model so it can retry."""

    async def awrap_tool_call(self, request, handler):
        result = await handler(request)
        if isinstance(result, ToolMessage) and result.status == "error":
            return Command(goto="model", update={"messages": [result]})
        return result


# Shown to the model on its last allowed call, so the run ends with an answer.
LAST_CALL_NOTICE = (
    "This is your last model call for this message: do not call any tool. Reply to the person "
    "now, in plain words, with what is done, what is not, and what you need from them."
)
# The reply when the model calls tools anyway on that last call.
OUT_OF_CALLS_REPLY = (
    "I have used all the steps I can take for this message. What I changed so far is in place; "
    "tell me how you would like to continue."
)


def _message_text(content: Any) -> str:
    """The text of a message's content, whether a string or content blocks"""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text" and isinstance(block.get("text"), str):
                parts.append(block["text"])
        return "\n".join(parts)
    return str(content or "")


def _ai_message(response: Any) -> Optional[AIMessage]:
    messages = response.result if isinstance(response, ModelResponse) else [response]
    return next((m for m in messages if isinstance(m, AIMessage)), None)


def _reply_instead(ai: AIMessage, text: str) -> AIMessage:
    """``ai`` turned into a plain reply, keeping its id and usage so the call is still billed"""
    return AIMessage(
        content=text,
        id=ai.id,
        usage_metadata=ai.usage_metadata,
        response_metadata=dict(ai.response_metadata or {}),
    )


def without_tool_calls(response: Any) -> Any:
    """``response`` with its tool calls dropped so the agent loop ends on it.

    The model's own text becomes the reply, or ``OUT_OF_CALLS_REPLY`` when it wrote
    none. Usage metadata survives so the call is still billed and counted."""
    ai = _ai_message(response)
    if ai is None or not ai.tool_calls:
        return response
    return _reply_instead(ai, _message_text(ai.content).strip() or OUT_OF_CALLS_REPLY)


def was_truncated(message: Any) -> bool:
    """Whether the provider cut this reply off at its output limit (max_tokens)"""
    metadata = getattr(message, "response_metadata", None) or {}
    stop = str(metadata.get("stop_reason") or metadata.get("finish_reason") or "").lower()
    return stop in ("max_tokens", "length")


def _configured_max_tokens(model: Any) -> Optional[int]:
    """The max_tokens of the chat model behind our wrappers, for the log line only"""
    for _ in range(4):
        if model is None:
            return None
        value = getattr(model, "max_tokens", None)
        if isinstance(value, int):
            return value
        model = getattr(model, "inner", None) or getattr(model, "bound", None)
    return None


# A tool call cut off by max_tokens cannot be run as the model meant it. Claude's API
# buffers each tool argument until it is complete, so the call arrives with empty
# arguments; OpenAI delivers the cut-off JSON, which parses as a partial object.
MAX_TRUNCATED_TOOL_CALLS = 2
TRUNCATED_CALL_HINT = (
    "This call was cut off by the model's output limit (max_tokens) before its arguments "
    "were complete, so it was not run. Make the call smaller: fewer operations per call and "
    "shorter texts, in several calls if needed."
)
OUTPUT_LIMIT_REPLY = (
    "I could not finish this request: the AI provider's output limit (Max Tokens) is lower "
    "than what my instructions need, so they were cut off before they could be applied. "
    "Nothing was changed. Raise Max Tokens on the LLM provider (16,000 is a safe value) and "
    "send the message again."
)


class TruncatedToolCallMiddleware(AgentMiddleware):
    """
    Stop a tool call the provider cut off at max_tokens from running or looping.

    The first time, the call is answered with a hint instead of being executed, so the
    model can make it smaller. The second time, the run ends with a reply that names the
    provider setting to change: a cap too low for the task is nothing the model can fix,
    and without this a 1,024-token cap cost a dozen identical retries per message.
    """

    def __init__(self) -> None:
        super().__init__()
        self.truncated = 0

    async def awrap_model_call(self, request, handler):
        response = await handler(request)
        ai = _ai_message(response)
        if ai is None or not ai.tool_calls or not was_truncated(ai):
            return response
        self.truncated += 1
        logger.warning(
            "Model output hit max_tokens (%s) in the middle of a tool call (%s), %d of %d allowed",
            _configured_max_tokens(request.model),
            ", ".join(str(call.get("name")) for call in ai.tool_calls),
            self.truncated,
            MAX_TRUNCATED_TOOL_CALLS,
        )
        if self.truncated < MAX_TRUNCATED_TOOL_CALLS:
            return response
        return _reply_instead(ai, OUTPUT_LIMIT_REPLY)

    async def awrap_tool_call(self, request, handler):
        if self._was_cut_off(request):
            return ToolMessage(
                content=TRUNCATED_CALL_HINT,
                tool_call_id=request.tool_call["id"],
                name=request.tool_call.get("name"),
                status="error",
            )
        return await handler(request)

    @staticmethod
    def _was_cut_off(request) -> bool:
        messages = (getattr(request, "state", None) or {}).get("messages") or []
        asked = next((m for m in reversed(messages) if isinstance(m, AIMessage)), None)
        if asked is None or not was_truncated(asked):
            return False
        return any(call.get("id") == request.tool_call.get("id") for call in asked.tool_calls)


class ModelCallBudgetMiddleware(AgentMiddleware):
    """
    Cap the model calls of one run and end it with a reply, not a recursion error.

    ``max_calls`` is the agent's maxIterations. The last allowed call carries a notice
    to answer without tools; if the model calls tools anyway, they are dropped and its
    text (or a fixed reply) ends the run. The graph's recursion limit stays the
    backstop behind this.
    """

    def __init__(self, max_calls: int) -> None:
        super().__init__()
        self.max_calls = max(1, int(max_calls or 1))
        self.calls = 0

    async def awrap_model_call(self, request, handler):
        self.calls += 1
        if self.calls < self.max_calls:
            return await handler(request)
        if self.calls == self.max_calls:
            logger.info("Agent reached its model-call budget (%d); asking for a final reply", self.max_calls)
        request = request.override(messages=[*request.messages, HumanMessage(content=LAST_CALL_NOTICE)])
        return without_tool_calls(await handler(request))


def _collect_llm_usage(messages: List[BaseMessage]) -> List[Dict[str, Any]]:
    """One usage entry per generated AIMessage; each is a billed model call"""
    entries = []
    for message in messages:
        if isinstance(message, AIMessage):
            try:
                usage = extract_usage_from_aimessage(message)
            except Exception:
                logger.warning("Failed extracting LLM usage from a ReActAgentLC message", exc_info=True)
                continue
            if usage:
                entries.append(usage)
    return entries


class ReActAgentLC(BaseToolAgent):
    """ReAct Agent implementation using LangGraph's prebuilt React agent"""

    system_prompt: Union[str, SystemMessage]

    def __init__(
        self,
        llm_model: BaseChatModel,
        system_prompt: Union[str, SystemMessage],
        tools: List[BaseTool],
        verbose: bool = False,
        max_iterations: int = 5,
        on_token: Optional["TokenSink"] = None,
    ):
        """Initialize a LangGraph ReAct agent

        Args:
            llm_model: The language model to use for reasoning and decision making
            system_prompt: System prompt that defines the agent's behavior and role.
                A SystemMessage is passed to create_agent unchanged, so its content
                blocks survive into the request
            tools: List of tools the agent can use to take actions
            verbose: Whether to enable verbose logging of reasoning cycles
            max_iterations: Maximum number of reasoning/action cycles
            on_token: Called with (model call id, text) as this agent's own model calls write
        """
        super().__init__(
            llm_model,
            system_prompt,
            tools,
            verbose=verbose,
            max_iterations=max_iterations,
        )
        self.on_token = on_token

        # Convert BaseTool instances to LangChain StructuredTool instances
        self.lc_tools = self._convert_tools_to_langchain(self.tools)

        # Create LangGraph React agent
        self.agent_executor = self._create_langgraph_agent()

        logger.info(
            f"ReActAgentLC initialized with {len(self.tools)} tools using LangGraph"
        )

    def _convert_tools_to_langchain(
        self, tools: List[BaseTool]
    ) -> List[StructuredTool]:
        """Convert BaseTool instances to LangChain StructuredTool instances"""
        lc_tools = []

        for tool in tools:
            # Create a wrapper function that handles the BaseTool interface
            # Use default parameter to capture the tool reference in closure
            def create_tool_wrapper(original_tool: BaseTool):
                async def tool_wrapper(**kwargs):
                    try:
                        result = await original_tool.invoke(**kwargs)
                        return result
                    except Exception as e:
                        logger.error(
                            f"Error executing tool {original_tool.name}: {str(e)}"
                        )
                        return f"Error executing tool {original_tool.name}: {str(e)}"

                return tool_wrapper

            # Create LangChain StructuredTool - use func instead of coroutine since our tools are sync
            lc_tool = StructuredTool.from_function(
                coroutine=create_tool_wrapper(tool),
                name=tool.name,
                description=tool.description,
                # Use the tool's parameters if available, otherwise empty schema
                args_schema=self._create_tool_schema(tool),
                # Pass through return_direct setting
                return_direct=getattr(tool, "return_direct", False),
            )
            lc_tools.append(lc_tool)

        return lc_tools

    @staticmethod
    def _as_text(value: Any) -> Any:
        """
        Accept a JSON object or array where the schema says string.

        Models regularly send a real array or object for a parameter described as
        "a JSON array" or "JSON text"; rejecting the call for that teaches them
        nothing and wastes a turn. The tool gets the same JSON it would have parsed.
        """
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return str(value)
        return value

    def _create_tool_schema(self, tool: BaseTool):
        """Create a Pydantic schema for the tool parameters"""
        from typing import Annotated

        from pydantic import BeforeValidator, Field, create_model

        # If the tool has parameters, create a dynamic Pydantic model
        if hasattr(tool, "parameters") and tool.parameters:
            fields = {}
            for param_name, param_info in tool.parameters.items():
                # Extract parameter info
                param_type = param_info.get("type", "string")
                param_description = param_info.get(
                    "description", f"Parameter {param_name}"
                )
                param_default = param_info.get("defaultValue", None)
                required = param_info.get("required", False)

                # Map parameter types to Python types
                if param_type == "string":
                    field_type = Annotated[str, BeforeValidator(self._as_text)]
                elif param_type == "integer":
                    field_type = int
                elif param_type == "number":
                    field_type = float
                elif param_type == "boolean":
                    field_type = bool
                elif param_type == "object":
                    field_type = dict
                elif param_type == "array":
                    field_type = list
                else:
                    field_type = Any

                # Create field definition for create_model
                if required:
                    fields[param_name] = (
                        field_type,
                        Field(description=param_description),
                    )
                else:
                    fields[param_name] = (
                        Optional[field_type],
                        Field(default=param_default, description=param_description),
                    )

            # Use create_model for Pydantic v2 compatibility
            schema_class = create_model(f"{tool.name.title()}Schema", **fields)
            return schema_class

        # Return None if no parameters (LangChain will handle this)
        return None

    def _create_langgraph_agent(self):
        """Create the LangGraph React agent executor"""
        # Create the agent with system prompt
        agent_executor = create_agent(
            model=self.llm_model,
            tools=self.lc_tools,
            system_prompt=self.system_prompt,
            middleware=[
                RetryOnToolErrorMiddleware(),
                TruncatedToolCallMiddleware(),
                ModelCallBudgetMiddleware(self.max_iterations),
            ],
        )

        return agent_executor

    def _extract_message_content(self, message) -> str:
        """Extract text content from a message, handling different formats"""
        if not hasattr(message, "content") or not message.content:
            return ""

        content = message.content

        # If content is a list (content blocks), extract text
        if isinstance(content, list):
            text_parts = []
            for block in content:
                if (
                    isinstance(block, dict)
                    and block.get("type") == "text"
                    and "text" in block
                ):
                    text_parts.append(block["text"])
                elif isinstance(block, str):
                    text_parts.append(block)
            content = "\n".join(text_parts) if text_parts else str(content)

        # Convert to string if not already
        if not isinstance(content, str):
            content = str(content)

        return content

    def _convert_chat_history_to_messages(self, chat_history: List[Dict[str, str]]):
        """Convert chat history to LangChain message format"""
        messages: List[BaseMessage] = []
        for message in chat_history:
            role = message.get("role", "user")
            # An older turn stored as the agent's whole output is reduced to its reply.
            content = history_text(message.get("content", ""))
            if not isinstance(content, str):
                content = json.dumps(content)

            if role in ["user", "human"]:
                messages.append(HumanMessage(content=content))
            elif role in ["agent", "assistant", "ai"]:
                messages.append(AIMessage(content=content))

        return messages

    async def _graph_states(self, input_data: Dict[str, Any], config: Dict[str, Any]) -> AsyncIterator[Dict[str, Any]]:
        modes = ["values", "tasks", "messages"] if self.on_token else ["values"]
        model_tasks: set[str] = set()
        async for mode, payload in self.agent_executor.astream(input_data, config=config, stream_mode=modes):
            if mode == "values":
                yield payload
            elif mode == "tasks":
                if payload.get("name") == "model":
                    model_tasks.add(payload["id"])
            else:
                # Only this graph's model tasks: an agent run inside a tool reports to the same handler.
                chunk, metadata = payload
                task_id = metadata.get("langgraph_checkpoint_ns", "").rpartition(":")[2]
                if isinstance(chunk, AIMessageChunk) and task_id in model_tasks and chunk.text:
                    self.on_token(task_id, chunk.text)

    async def invoke(
        self, query: str, chat_history: Optional[List] = None, **kwargs
    ) -> Dict[str, Any]:
        """Execute a query using the LangGraph ReAct agent"""
        chat_history = chat_history or []
        thread_id = kwargs.get("thread_id", str(uuid.uuid4()))
        result: Dict[str, Any] = {}
        input_message_count = 0

        try:
            # Prepare the input for LangGraph
            messages: List[BaseMessage] = []

            # Add chat history if available
            if chat_history:
                history_messages = self._convert_chat_history_to_messages(chat_history)
                messages.extend(history_messages)

            # Add the current query
            messages.append(HumanMessage(content=query))

            input_data = {"messages": messages}
            input_message_count = len(messages)

            # Configure the execution
            config = {
                "recursion_limit": self.max_iterations * 2 + 1,
                "configurable": {
                    "thread_id": thread_id,
                },
            }
            # Track reasoning steps and tools used
            reasoning_steps = []
            tools_used = []

            # Execute the agent
            if self.verbose:
                logger.debug(f"Executing LangGraph ReAct agent with query: {query}")

            # ainvoke runs this same loop but discards the state when the graph raises
            async for state in self._graph_states(input_data, config):
                result = state

            if self.verbose:
                logger.debug(f"LangGraph agent result: {result}")

            # Extract final response and build reasoning steps from all messages
            final_response = None
            return_direct_tool_name = None
            return_direct_tool_result = None

            if "messages" in result and result["messages"]:
                # Only process messages generated by the agent, not input/history
                agent_messages = result["messages"][input_message_count:]

                # First pass: track tools with return_direct and find their results
                tool_call_to_name_map = {}  # Map tool_call_id to tool_name

                for message in agent_messages:
                    # Track tool calls and their names
                    if isinstance(message, AIMessage):
                        if hasattr(message, "tool_calls") and message.tool_calls:
                            tool_calls_list = (
                                message.tool_calls
                                if isinstance(message.tool_calls, list)
                                else [message.tool_calls]
                            )
                            for tool_call in tool_calls_list:
                                if isinstance(tool_call, dict):
                                    tool_name = tool_call.get("name", "unknown")
                                    tool_call_id = tool_call.get("id", "")
                                else:
                                    tool_name = getattr(tool_call, "name", "unknown")
                                    tool_call_id = getattr(tool_call, "id", "")

                                # Check if this tool has return_direct=True
                                if tool_name in self.tool_map:
                                    tool = self.tool_map[tool_name]
                                    if (
                                        hasattr(tool, "return_direct")
                                        and tool.return_direct
                                    ):
                                        return_direct_tool_name = tool_name
                                        tool_call_to_name_map[tool_call_id] = tool_name

                    # Check for ToolMessage results from return_direct tools
                    if isinstance(message, ToolMessage):
                        tool_call_id = getattr(message, "tool_call_id", "")
                        if tool_call_id in tool_call_to_name_map:
                            # This is a result from a return_direct tool
                            return_direct_tool_result = self._extract_message_content(
                                message
                            )
                            return_direct_tool_name = tool_call_to_name_map[
                                tool_call_id
                            ]
                            if self.verbose:
                                logger.debug(
                                    f"Found return_direct tool result from {return_direct_tool_name}: {return_direct_tool_result}"
                                )

                # Process only agent-generated messages to extract reasoning steps
                for message in agent_messages:
                    if not isinstance(message, AIMessage):
                        continue

                    # Extract content
                    content = (
                        self._extract_message_content(message)
                        if hasattr(message, "content")
                        else ""
                    )

                    # Check for tool calls
                    tool_calls_list = []
                    if hasattr(message, "tool_calls") and message.tool_calls:
                        tool_calls_list = (
                            message.tool_calls
                            if isinstance(message.tool_calls, list)
                            else [message.tool_calls]
                        )

                    has_tool_calls = len(tool_calls_list) > 0
                    has_content = bool(content and content.strip())

                    # Process tool calls
                    if has_tool_calls:
                        for tool_call in tool_calls_list:
                            # Extract tool information
                            if isinstance(tool_call, dict):
                                tool_name = tool_call.get("name", "unknown")
                                tool_args = tool_call.get("args", {})
                            else:
                                tool_name = getattr(tool_call, "name", "unknown")
                                tool_args = getattr(tool_call, "args", {})

                            # Add to tools_used
                            tools_used.append(
                                {
                                    "tool_name": tool_name,
                                    "args": tool_args,
                                    "iteration": len(tools_used) + 1,
                                }
                            )

                            # Create reasoning step with tool call information
                            thought = (
                                content.strip()
                                if content and content.strip()
                                else f"Using tool '{tool_name}' to get information."
                            )

                            reasoning_steps.append(
                                {
                                    "iteration": len(reasoning_steps) + 1,
                                    "thought": thought,
                                    "full_response": thought,
                                    "tool_name": tool_name,
                                    "tool_args": tool_args,
                                }
                            )

                    # Process non-tool-call messages with content (these are intermediate or final responses)
                    elif has_content and not has_tool_calls:
                        # Try to parse JSON response
                        parsed_json = parse_json_response(content)
                        if parsed_json:
                            # Extract from JSON if available
                            thought = parsed_json.get("thought") or parsed_json.get(
                                "message", content
                            )
                            # Check if JSON has steps to extract
                            if "steps" in parsed_json and isinstance(
                                parsed_json["steps"], list
                            ):
                                for step in parsed_json["steps"]:
                                    if isinstance(step, dict):
                                        reasoning_steps.append(
                                            {
                                                "iteration": step.get(
                                                    "iteration",
                                                    len(reasoning_steps) + 1,
                                                ),
                                                "thought": step.get(
                                                    "thought",
                                                    step.get("full_response", ""),
                                                ),
                                                "full_response": step.get(
                                                    "full_response",
                                                    step.get("thought", ""),
                                                ),
                                            }
                                        )
                        else:
                            thought = content

                        # Add as reasoning step (will identify final response later)
                        reasoning_steps.append(
                            {
                                "iteration": len(reasoning_steps) + 1,
                                "thought": thought,
                                "full_response": content,
                            }
                        )

                # If we found a return_direct tool result, use it as the final response
                if return_direct_tool_result is not None:
                    final_response = return_direct_tool_result
                    if self.verbose:
                        logger.debug(
                            f"Using return_direct tool result as final response: {final_response}"
                        )
                # Fallback: check if the last message is a ToolMessage (might be return_direct)
                elif agent_messages and isinstance(
                    agent_messages[-1], ToolMessage
                ):
                    last_message = agent_messages[-1]
                    tool_call_id = getattr(last_message, "tool_call_id", "")
                    # Look up the tool name from our mapping
                    if tool_call_id in tool_call_to_name_map:
                        tool_name_from_msg = tool_call_to_name_map[tool_call_id]
                        if tool_name_from_msg in self.tool_map:
                            tool = self.tool_map[tool_name_from_msg]
                            if hasattr(tool, "return_direct") and tool.return_direct:
                                final_response = self._extract_message_content(
                                    last_message
                                )
                                return_direct_tool_name = tool_name_from_msg
                                if self.verbose:
                                    logger.debug(
                                        f"Found return_direct tool result in last message from {return_direct_tool_name}: {final_response}"
                                    )
                # Otherwise, identify the final response (last AI message without tool calls)
                elif agent_messages:
                    for message in reversed(agent_messages):
                        if isinstance(message, AIMessage):
                            content = (
                                self._extract_message_content(message)
                                if hasattr(message, "content")
                                else ""
                            )
                            has_tool_calls = bool(
                                hasattr(message, "tool_calls") and message.tool_calls
                            )

                            if content and content.strip() and not has_tool_calls:
                                parsed_json = parse_json_response(content)
                                if parsed_json and "message" in parsed_json:
                                    final_response = parsed_json.get("message", content)
                                else:
                                    final_response = content
                                break

            # Extract final answer
            if final_response:
                # Build response data
                response_data = {
                    "iterations": len(reasoning_steps),
                    "reasoning_steps": reasoning_steps,
                    "tools_used": tools_used,
                    "thread_id": thread_id,
                }

                # Add return_direct info if applicable
                if return_direct_tool_name:
                    response_data["return_direct"] = True
                    response_data["tool"] = return_direct_tool_name

                response = create_success_response(
                    final_response,
                    self._get_agent_name(),
                    **response_data,
                )
            else:
                response = create_error_response(
                    "No response generated by LangGraph agent",
                    self._get_agent_name(),
                    thread_id=thread_id,
                )

        except Exception as e:
            logger.error(f"Error executing ReActAgentLC query: {str(e)}")
            response = create_error_response(
                str(e), self._get_agent_name(), thread_id=thread_id
            )

        llm_usage_entries = _collect_llm_usage(result.get("messages", [])[input_message_count:])
        if llm_usage_entries:
            response["llm_usage"] = llm_usage_entries
        return response

    # ==================== TOOL MANAGEMENT ====================
    # Tool management methods are inherited from BaseToolAgent

    def add_tool(self, tool: BaseTool):
        """Add a new tool to the agent and recreate the LangGraph agent"""
        super().add_tool(tool)
        # Convert new tools and recreate agent
        self.lc_tools = self._convert_tools_to_langchain(self.tools)
        self.agent_executor = self._create_langgraph_agent()

    def remove_tool(self, tool_name: str) -> bool:
        """Remove a tool from the agent and recreate the LangGraph agent"""
        success = super().remove_tool(tool_name)
        if success:
            # Convert remaining tools and recreate agent
            self.lc_tools = self._convert_tools_to_langchain(self.tools)
            self.agent_executor = self._create_langgraph_agent()
        return success
