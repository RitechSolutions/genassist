"""Makes an agent's first move on each message a call to one chosen tool"""

import logging
import uuid
from typing import Any, Dict, List, Optional, Tuple

from langchain.agents.middleware.types import AgentMiddleware, ModelResponse
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from app.core.utils.sensitive_data_utils import redact_sensitive_substrings
from app.core.utils.string_utils import truncate_for_log
from app.modules.workflow.llm.fallback_exceptions import _extract_status_code, is_retryable

logger = logging.getLogger(__name__)

NAMED_TOOL_CHOICE = "tool"
THINKING_ON_TYPES = ("enabled", "adaptive")
ACCOUNT_ERROR_STATUSES = (401, 403, 404)
IGNORES_TOOL_CHOICE = ("ChatOllama",)
CATCH_ALL_INPUT = "kwargs"
TEXT_INPUT_TYPE = "string"


def _fails_every_call(error: Exception) -> bool:
    """Outages and account errors would fail the next model call too"""
    return is_retryable(error) or _extract_status_code(error) in ACCOUNT_ERROR_STATUSES


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


def _ignores_named_tool(model: Any) -> bool:
    """True when the model cannot bind a named tool, or accepts the setting but ignores it"""
    if type(model).__name__ in IGNORES_TOOL_CHOICE:
        return True
    supported_choices = getattr(model, "supports_tool_choice_values", None)
    choices_are_listed = supported_choices is not None
    return choices_are_listed and NAMED_TOOL_CHOICE not in supported_choices


def model_can_be_told_which_tool(model: Any) -> bool:
    """False when any model cannot bind a named tool, or the model tried first has thinking on"""
    models = _models_behind(model)
    if any(_ignores_named_tool(each_model) for each_model in models):
        return False
    return not _thinking_is_on(models[0])


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


def _input_schema(tool: Any) -> Optional[Tuple[Dict[str, Any], List[str]]]:
    """The tool's inputs and required input names, leaving out the catch-all of a tool with no inputs"""
    try:
        schema = tool.get_input_schema().model_json_schema()
    except Exception:
        return None
    properties = {name: spec for name, spec in (schema.get("properties") or {}).items() if name != CATCH_ALL_INPUT}
    required = [name for name in (schema.get("required") or []) if name in properties]
    return properties, required


def _single_input(properties: Dict[str, Any], required: List[str]) -> Optional[str]:
    """The tool's only required input, or its only input"""
    if len(required) == 1:
        return required[0]
    if len(properties) == 1:
        return next(iter(properties))
    return None


def _accepts_text(spec: Dict[str, Any]) -> bool:
    allowed_types = {spec.get("type")} | {option.get("type") for option in spec.get("anyOf") or []}
    return TEXT_INPUT_TYPE in allowed_types


def _direct_call_args(tool: Any, user_text: str) -> Tuple[Optional[Dict[str, Any]], str]:
    """Arguments that fill the tool from the user's message, or None and the reason it cannot be done"""
    schema = _input_schema(tool)
    if schema is None:
        return None, "its inputs could not be read"
    properties, required = schema
    if not properties:
        return {}, ""
    input_name = _single_input(properties, required)
    if input_name is None:
        return None, "it needs more than one input"
    if not _accepts_text(properties[input_name]):
        return None, f"its input '{input_name}' does not take text"
    return {input_name: user_text}, ""


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
        """Reply when told to call the tool, None if it cannot be told or refuses; outage and account errors raise"""
        if not model_can_be_told_which_tool(request.model):
            return None
        try:
            response = await handler(request.override(tool_choice=self.tool_name))
        except Exception as error:
            if _fails_every_call(error):
                raise
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
        user_messages = [message for message in request.messages if isinstance(message, HumanMessage)]
        if not user_messages:
            logger.warning(f"'{self.tool_name}' cannot be called with the user's message: there is no user message")
            return None
        args, reason = _direct_call_args(tool, user_messages[-1].text)
        if args is None:
            logger.warning(f"'{self.tool_name}' cannot be called with the user's message: {reason}")
            return None
        tool_call = {
            "name": self.tool_name,
            "args": args,
            "id": f"call_{uuid.uuid4().hex}",
            "type": "tool_call",
        }
        return ModelResponse(result=[AIMessage(content="", tool_calls=[tool_call])])
