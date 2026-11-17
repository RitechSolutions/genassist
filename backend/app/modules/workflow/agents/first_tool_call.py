"""Makes an agent's first move on each message a call to one chosen tool"""

import logging
import uuid
from typing import Any, List, Optional

from langchain.agents.middleware.types import AgentMiddleware, ModelResponse
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

logger = logging.getLogger(__name__)

NAMED_TOOL_CHOICE = "tool"


def model_can_be_told_which_tool(model: Any) -> bool:
    """False when the model, or any model of its fallback chain, says it cannot be made to call a named tool"""
    for each_model in getattr(model, "models", None) or [model]:
        supported_choices = getattr(each_model, "supports_tool_choice_values", None)
        if supported_choices is not None and NAMED_TOOL_CHOICE not in supported_choices:
            return False
    return True


def _messages_since_user_message(messages: List[BaseMessage]) -> List[BaseMessage]:
    last_user_index = max((i for i, m in enumerate(messages) if isinstance(m, HumanMessage)), default=-1)
    return messages[last_user_index + 1:]


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
    """Before the agent answers a message, it calls the chosen tool once.

    The model is told to call the tool and writes the tool's input itself. If the model
    cannot be told, or does not call it, the tool is called with the user's message.
    """

    def __init__(self, tool_name: str):
        super().__init__()
        self.tool_name = tool_name

    async def awrap_model_call(self, request, handler):
        if not self._is_first_move(request):
            return await handler(request)

        response = None
        if model_can_be_told_which_tool(request.model):
            response = await handler(request.override(tool_choice=self.tool_name))
            if _calls_tool(response, self.tool_name):
                return response
            logger.warning(f"The model did not call '{self.tool_name}' when told to; calling it with the user's message")

        direct_call = self._call_with_user_message(request)
        if direct_call is not None:
            return direct_call
        return response if response is not None else await handler(request)

    def _is_first_move(self, request) -> bool:
        tool_offered = any(_tool_name(tool) == self.tool_name for tool in request.tools)
        model_moved_already = any(isinstance(m, AIMessage) for m in _messages_since_user_message(request.messages))
        return tool_offered and not model_moved_already

    def _call_with_user_message(self, request) -> Optional[ModelResponse]:
        tool = next(tool for tool in request.tools if _tool_name(tool) == self.tool_name)
        input_name = _single_input_name(tool)
        user_messages = [m for m in request.messages if isinstance(m, HumanMessage)]
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
