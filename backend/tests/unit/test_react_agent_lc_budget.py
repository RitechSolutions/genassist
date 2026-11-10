"""ReActAgentLC: the per-run model-call budget and reply-only history"""

from unittest.mock import MagicMock, patch

import pytest
from langchain.agents.middleware.types import ModelRequest, ModelResponse
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.modules.workflow.agents.react_agent_lc import (
    LAST_CALL_NOTICE,
    OUT_OF_CALLS_REPLY,
    OUTPUT_LIMIT_REPLY,
    TRUNCATED_CALL_HINT,
    ModelCallBudgetMiddleware,
    ReActAgentLC,
    RetryOnToolErrorMiddleware,
    TruncatedToolCallMiddleware,
    was_truncated,
    without_tool_calls,
)

_CREATE_AGENT = "app.modules.workflow.agents.react_agent_lc.create_agent"


def _request(*messages):
    return ModelRequest(model=MagicMock(), messages=list(messages))


def _tool_call_message(text=""):
    return AIMessage(
        content=text,
        tool_calls=[{"name": "search", "args": {"q": "x"}, "id": "call_1", "type": "tool_call"}],
        usage_metadata={"input_tokens": 11, "output_tokens": 7, "total_tokens": 18},
    )


class _Handler:
    """Records the requests it is given and answers with the queued messages"""

    def __init__(self, *answers):
        self.answers = list(answers)
        self.requests = []

    async def __call__(self, request):
        self.requests.append(request)
        return ModelResponse(result=[self.answers.pop(0)])


@pytest.mark.asyncio
async def test_calls_under_the_budget_pass_through_untouched():
    middleware = ModelCallBudgetMiddleware(max_calls=3)
    handler = _Handler(_tool_call_message(), _tool_call_message())
    request = _request(HumanMessage(content="hi"))

    first = await middleware.awrap_model_call(request, handler)
    second = await middleware.awrap_model_call(request, handler)

    assert handler.requests == [request, request]
    assert first.result[0].tool_calls and second.result[0].tool_calls


@pytest.mark.asyncio
async def test_the_last_allowed_call_asks_for_a_reply_and_drops_tool_calls():
    middleware = ModelCallBudgetMiddleware(max_calls=2)
    handler = _Handler(_tool_call_message(), _tool_call_message("Adding the step now."))
    request = _request(HumanMessage(content="hi"), _tool_call_message(), ToolMessage(content="ok", tool_call_id="call_1"))

    await middleware.awrap_model_call(request, handler)
    final = await middleware.awrap_model_call(request, handler)

    sent = handler.requests[1].messages
    assert isinstance(sent[-1], HumanMessage) and sent[-1].content == LAST_CALL_NOTICE
    assert len(sent) == len(request.messages) + 1
    # The original request is left alone (override is immutable).
    assert len(request.messages) == 3
    assert isinstance(final, AIMessage)
    assert final.tool_calls == []
    assert final.content == "Adding the step now."
    # The call is still billed.
    assert final.usage_metadata == {"input_tokens": 11, "output_tokens": 7, "total_tokens": 18}


@pytest.mark.asyncio
async def test_a_silent_tool_call_on_the_last_call_becomes_the_fixed_reply():
    middleware = ModelCallBudgetMiddleware(max_calls=1)
    handler = _Handler(_tool_call_message())

    final = await middleware.awrap_model_call(_request(HumanMessage(content="hi")), handler)

    assert final.content == OUT_OF_CALLS_REPLY and final.tool_calls == []


@pytest.mark.asyncio
async def test_a_plain_reply_on_the_last_call_is_returned_as_is():
    middleware = ModelCallBudgetMiddleware(max_calls=1)
    reply = AIMessage(content="All done.")
    handler = _Handler(reply)

    final = await middleware.awrap_model_call(_request(HumanMessage(content="hi")), handler)

    assert isinstance(final, ModelResponse) and final.result == [reply]


def test_without_tool_calls_reads_text_from_content_blocks():
    blocks = AIMessage(
        content=[{"type": "text", "text": "Nearly there."}, {"type": "tool_use", "id": "t1", "name": "x", "input": {}}],
        tool_calls=[{"name": "x", "args": {}, "id": "t1", "type": "tool_call"}],
    )
    assert without_tool_calls(blocks).content == "Nearly there."
    untouched = AIMessage(content="no tools here")
    assert without_tool_calls(untouched) is untouched


def test_budget_never_drops_below_one_call():
    assert ModelCallBudgetMiddleware(max_calls=0).max_calls == 1
    assert ModelCallBudgetMiddleware(max_calls=None).max_calls == 1


def test_agent_installs_the_budget_sized_by_max_iterations():
    with patch(_CREATE_AGENT, return_value=MagicMock()) as create_agent:
        ReActAgentLC(llm_model=MagicMock(), system_prompt="be useful", tools=[], max_iterations=16)

    middleware = create_agent.call_args.kwargs["middleware"]
    assert [type(m) for m in middleware] == [
        RetryOnToolErrorMiddleware,
        TruncatedToolCallMiddleware,
        ModelCallBudgetMiddleware,
    ]
    assert middleware[2].max_calls == 16


def test_history_sends_only_the_reply_of_a_stored_agent_turn():
    with patch(_CREATE_AGENT, return_value=MagicMock()):
        agent = ReActAgentLC(llm_model=MagicMock(), system_prompt="be useful", tools=[])

    history = [
        {"role": "user", "content": "Build me a bot"},
        {
            "role": "assistant",
            "content": {
                "message": "Built it.",
                "steps": [{"tool_name": "apply_plan", "tool_args": {"operations": "[...]" * 500}}],
                "tools_used": [{"tool_name": "apply_plan"}],
            },
        },
        {"role": "assistant", "content": {"answer": 42}},
    ]
    messages = agent._convert_chat_history_to_messages(history)

    assert [m.content for m in messages] == ["Build me a bot", "Built it.", '{"answer": 42}']



# ── Tool calls cut off by the provider's output limit ─────────────────────


def _cut_off_call(name="apply_plan", call_id="call_1", stop="max_tokens"):
    """What Claude returns when max_tokens hits mid tool call: the call, no arguments"""
    return AIMessage(
        content=[{"type": "tool_use", "id": call_id, "name": name, "input": {}, "partial_json": ""}],
        tool_calls=[{"name": name, "args": {}, "id": call_id, "type": "tool_call"}],
        response_metadata={"stop_reason": stop},
        usage_metadata={"input_tokens": 7000, "output_tokens": 1024, "total_tokens": 8024},
    )


def _tool_request(ai_message, call_id="call_1"):
    return SimpleNamespace(
        tool_call={"name": "apply_plan", "args": {}, "id": call_id},
        state={"messages": [HumanMessage(content="build it"), ai_message]},
    )


@pytest.mark.parametrize(
    "metadata,expected",
    [
        ({"stop_reason": "max_tokens"}, True),
        ({"finish_reason": "length"}, True),
        ({"stop_reason": "tool_use"}, False),
        ({"finish_reason": "tool_calls"}, False),
        ({}, False),
    ],
)
def test_was_truncated_reads_both_providers_stop_reasons(metadata, expected):
    assert was_truncated(AIMessage(content="", response_metadata=metadata)) is expected


@pytest.mark.asyncio
async def test_a_cut_off_tool_call_is_answered_with_a_hint_and_never_run():
    middleware = TruncatedToolCallMiddleware()
    handler = AsyncMock()

    result = await middleware.awrap_tool_call(_tool_request(_cut_off_call()), handler)

    handler.assert_not_awaited()
    assert isinstance(result, ToolMessage)
    assert result.status == "error" and result.tool_call_id == "call_1" and result.name == "apply_plan"
    assert result.content == TRUNCATED_CALL_HINT


@pytest.mark.asyncio
async def test_an_intact_tool_call_runs_normally():
    middleware = TruncatedToolCallMiddleware()
    intact = AIMessage(
        content="",
        tool_calls=[{"name": "apply_plan", "args": {"operations": "[]"}, "id": "call_1", "type": "tool_call"}],
        response_metadata={"stop_reason": "tool_use"},
    )
    expected = ToolMessage(content="Applied 1 of 1 operations.", tool_call_id="call_1")
    handler = AsyncMock(return_value=expected)

    assert await middleware.awrap_tool_call(_tool_request(intact), handler) is expected
    handler.assert_awaited_once()


@pytest.mark.asyncio
async def test_a_call_from_an_earlier_intact_message_is_not_mistaken_for_the_cut_off_one():
    middleware = TruncatedToolCallMiddleware()
    other_call = _cut_off_call(call_id="call_9")
    handler = AsyncMock(return_value=ToolMessage(content="ok", tool_call_id="call_1"))

    await middleware.awrap_tool_call(_tool_request(other_call, call_id="call_1"), handler)

    handler.assert_awaited_once()


@pytest.mark.asyncio
async def test_the_second_cut_off_call_ends_the_run_naming_the_provider_setting():
    middleware = TruncatedToolCallMiddleware()
    first, second = _cut_off_call(), _cut_off_call(call_id="call_2")
    handler = _Handler(first, second)
    request = _request(HumanMessage(content="build it"))

    passed_through = await middleware.awrap_model_call(request, handler)
    final = await middleware.awrap_model_call(request, handler)

    # The first one goes on to the tool hook, which answers it with the hint.
    assert isinstance(passed_through, ModelResponse) and passed_through.result == [first]
    # The second ends the turn: the model cannot raise the provider's cap itself.
    assert isinstance(final, AIMessage)
    assert final.tool_calls == [] and final.content == OUTPUT_LIMIT_REPLY
    assert final.usage_metadata == second.usage_metadata


@pytest.mark.asyncio
async def test_complete_model_calls_do_not_count_towards_the_cut_off_limit():
    middleware = TruncatedToolCallMiddleware()
    complete = AIMessage(
        content="",
        tool_calls=[{"name": "lookup_node", "args": {"query": "switchNode"}, "id": "c", "type": "tool_call"}],
        response_metadata={"stop_reason": "tool_use"},
    )
    handler = _Handler(complete, complete, _cut_off_call())
    request = _request(HumanMessage(content="hi"))

    for _ in range(3):
        result = await middleware.awrap_model_call(request, handler)

    assert middleware.truncated == 1
    assert isinstance(result, ModelResponse)  # first truncation still passes through
