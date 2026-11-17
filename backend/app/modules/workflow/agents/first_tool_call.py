"""Makes an agent's first move on each message a call to one chosen tool"""

import logging
import uuid
from typing import Any, List, Optional

from langchain.agents.middleware.types import AgentMiddleware, ModelResponse
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from app.core.utils.sensitive_data_utils import redact_sensitive_substrings
from app.core.utils.string_utils import truncate_for_log

logger = logging.getLogger(__name__)

NAMED_TOOL_CHOICE = "tool"
THINKING_ON_TYPES = ("enabled", "adaptive")


def _models_behind(model: Any) -> List[Any]:
    """The chat models a fallback chain or a prompt-caching wrapper sends requests to"""
    fallback_models = getattr(model, "models", None)
    if fallback_models:
        return [inner for each_model in fallback_models for inner in _models_behind(each_model)]
    wrapped_model = getattr(model, "inner", None)
    if wrapped_model is not None:
        return _models_behind(wrapped_model)
    return [model]


def _thinking_is_on(model: Any) -> bool:
    """Anthropic rejects a forced tool call while extended thinking is on"""
    thinking = getattr(model, "thinking", None)
    return isinstance(thinking, dict) and thinking.get("type") in THINKING_ON_TYPES


def model_can_be_told_which_tool(model: Any) -> bool:
    """False when any model behind it cannot be made to call a named tool"""
    for each_model in _models_behind(model):
        supported_choices = getattr(each_model, "supports_tool_choice_values", None)
        named_tool_unsupported = supported_choices is not None and NAMED_TOOL_CHOICE not in supported_choices
        if named_tool_unsupported or _thinking_is_on(each_model):
            return False
    return True


def _messages_since_user_message(messages: List[BaseMessage]) -> List[BaseMessage]:
    user_message_positions = [position for position, message in enumerate(messages) if isinstance(message, HumanMessage)]
    last_user_position = user_message_positions[-1] if user_message_positions else -1
    return messages[last_user_position + 1:]


def _tool_name(tool: Any) -> Optional[str]:
    return tool.get("name") if isinstance(tool, dict) else getattr(tool, "name", None)


def _calls_tool(response: Any, tool_name: str) -> bool:
    messages = response.result if isinstance(response, ModelResponse) else [response]
    return any(
        call.get("name") == tool_name
        for message in messages
        for call in (getattr(message, "tool_calls", None) or [])
    )


def _single_input_name(tool: Any) -> Optional[str]:
    """The tool's only required input, or its only input, so it can be filled with the user's message"""
    try:
        schema = tool.get_input_schema().model_json_schema()
    except Exception:
        return None
    names = list((schema.get("properties") or {}).keys())
    required = schema.get("required") or []
    if len(required) == 1:
        return required[0]
    return names[0] if len(names) == 1 else None


class FirstToolCallMiddleware(AgentMiddleware):
    """Calls the chosen tool before the agent answers each message"""

    def __init__(self, tool_name: str):
        super().__init__()
        self.tool_name = tool_name

    async def awrap_model_call(self, request, handler):
        if not self._is_first_move(request):
            return await handler(request)

        response = await self._told_to_call_tool(request, handler)
        if response is not None and _calls_tool(response, self.tool_name):
            return response

        direct_call = self._call_with_user_message(request)
        if direct_call is not None:
            return direct_call
        return response if response is not None else await handler(request)

    async def _told_to_call_tool(self, request, handler) -> Optional[Any]:
        """The model's reply when told to call the tool, or None when it cannot be told or refuses"""
        if not model_can_be_told_which_tool(request.model):
            return None
        try:
            response = await handler(request.override(tool_choice=self.tool_name))
        except Exception as error:
            reason = truncate_for_log(redact_sensitive_substrings(str(error)))
            logger.warning(
                f"The model refused to be told to call '{self.tool_name}' ({type(error).__name__}: {reason}); "
                "calling it with the user's message"
            )
            return None
        if not _calls_tool(response, self.tool_name):
            logger.warning(f"The model did not call '{self.tool_name}' when told to; calling it with the user's message")
        return response

    def _is_first_move(self, request) -> bool:
        tool_offered = any(_tool_name(tool) == self.tool_name for tool in request.tools)
        recent_messages = _messages_since_user_message(request.messages)
        model_moved_already = any(isinstance(message, AIMessage) for message in recent_messages)
        return tool_offered and not model_moved_already

    def _call_with_user_message(self, request) -> Optional[ModelResponse]:
        tool = next(tool for tool in request.tools if _tool_name(tool) == self.tool_name)
        input_name = _single_input_name(tool)
        user_messages = [message for message in request.messages if isinstance(message, HumanMessage)]
        if input_name is None or not user_messages:
            logger.warning(f"'{self.tool_name}' cannot be called with the user's message: it needs more than one input")
            return None
        tool_call = {
            "name": self.tool_name,
            "args": {input_name: user_messages[-1].text},
            "id": f"call_{uuid.uuid4().hex}",
            "type": "tool_call",
        }
        return ModelResponse(result=[AIMessage(content="", tool_calls=[tool_call])])
