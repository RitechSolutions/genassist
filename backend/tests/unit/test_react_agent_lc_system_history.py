"""Tests for ReActAgentLC: system content from the chat history reaches the model in the system prompt"""

import pytest
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage, SystemMessage
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult

from app.modules.workflow.agents.base_tool import BaseTool
from app.modules.workflow.agents.conversation_rag_indexer import ConversationRAGIndexer
from app.modules.workflow.agents.memory import InMemoryConversationMemory
from app.modules.workflow.agents.react_agent_lc import QUOTED_HISTORY_NOTICE, ReActAgentLC
from app.modules.workflow.llm.prompt_caching_chat_model import (
    PromptCachingChatModel,
    build_cacheable_system_message,
)

PROMPT = "You are a helpful Acme agent."
STABLE = "You are a helpful Acme agent with a long stable prefix."
VOLATILE = " Current time: 2026-08-17 12:00:00"
QUESTION = "What was my order number?"
ACME_BLOCK = ConversationRAGIndexer._format_retrieved_block(["User: My Acme order number is 48213."])
GLOBEX_BLOCK = ConversationRAGIndexer._format_retrieved_block(["User: My Globex order number is 77001."])
QUOTED_ACME_BLOCK = f"{QUOTED_HISTORY_NOTICE}\n\n{ACME_BLOCK}"
QUOTED_GLOBEX_BLOCK = f"{QUOTED_HISTORY_NOTICE}\n\n{GLOBEX_BLOCK}"
RECENT_TURN = [
    {"role": "user", "content": "Please explain sensors."},
    {"role": "assistant", "content": "Here is how sensors works."},
]
RECENT_TURN_MESSAGES = [
    HumanMessage(content="Please explain sensors."),
    AIMessage(content="Here is how sensors works."),
]


def _retrieved(block: str) -> dict:
    return {"role": "system", "content": block, "message_type": "rag_retrieved_history"}


class RecordingChatModel(BaseChatModel):
    """Answers every call and keeps the messages it was sent."""

    seen: list = []

    @property
    def _llm_type(self) -> str:
        return "recording"

    def bind_tools(self, tools, **kwargs):
        return self

    def _reply(self, messages) -> AIMessage:
        return AIMessage(content="the answer")

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        self.seen.append(list(messages))
        return ChatResult(generations=[ChatGeneration(message=self._reply(messages))])

    async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        return self._generate(messages, stop, run_manager, **kwargs)


class ToolThenAnswerChatModel(RecordingChatModel):
    """Calls the lookup tool on its first call, then answers."""

    def _reply(self, messages) -> AIMessage:
        is_first_call = len(self.seen) == 1
        if is_first_call:
            return AIMessage(
                content="", tool_calls=[{"name": "lookup", "args": {}, "id": "call_1", "type": "tool_call"}]
            )
        return AIMessage(content="the answer")


class StreamingChatModel(RecordingChatModel):
    """Writes its answer in two pieces."""

    async def _astream(self, messages, stop=None, run_manager=None, **kwargs):
        self.seen.append(list(messages))
        for piece in ["the ", "answer"]:
            yield ChatGenerationChunk(message=AIMessageChunk(content=piece))


def _sent(message) -> tuple:
    return (type(message).__name__, message.content)


def _sent_list(messages) -> list:
    return [_sent(message) for message in messages]


def _agent(system_prompt=PROMPT):
    model = RecordingChatModel()
    return ReActAgentLC(llm_model=model, system_prompt=system_prompt, tools=[]), model


@pytest.mark.asyncio
async def test_retrieved_block_reaches_the_model_at_the_end_of_the_system_prompt():
    agent, model = _agent()

    result = await agent.invoke(QUESTION, chat_history=[_retrieved(ACME_BLOCK), *RECENT_TURN])

    assert result["status"] == "success"
    assert result["response"] == "the answer"
    assert result["iterations"] == 1
    assert _sent_list(model.seen[-1]) == [
        ("SystemMessage", f"{PROMPT}\n\n{QUOTED_ACME_BLOCK}"),
        *_sent_list(RECENT_TURN_MESSAGES),
        ("HumanMessage", QUESTION),
    ]


@pytest.mark.asyncio
async def test_system_entries_keep_their_order_and_label():
    agent, model = _agent()
    history = [_retrieved(ACME_BLOCK), *RECENT_TURN, {"role": "system", "content": "Second system note."}]

    await agent.invoke(QUESTION, chat_history=history)

    sent = model.seen[-1]
    assert sent[0].content == f"{PROMPT}\n\n{QUOTED_HISTORY_NOTICE}\n\n{ACME_BLOCK}\n\nSecond system note."
    assert sent[0].content.count("[Relevant Conversation History]") == 1
    assert sent[0].content.count(QUOTED_HISTORY_NOTICE) == 1
    assert [type(message) for message in sent] == [SystemMessage, HumanMessage, AIMessage, HumanMessage]


@pytest.mark.asyncio
async def test_history_without_system_entries_is_sent_unchanged():
    agent, model = _agent()

    await agent.invoke(QUESTION, chat_history=RECENT_TURN)

    assert _sent_list(model.seen[-1]) == [
        ("SystemMessage", PROMPT),
        *_sent_list(RECENT_TURN_MESSAGES),
        ("HumanMessage", QUESTION),
    ]


@pytest.mark.asyncio
async def test_block_system_prompt_without_system_entries_is_sent_unchanged():
    system_message = build_cacheable_system_message(STABLE, VOLATILE)
    agent, model = _agent(system_message)

    await agent.invoke(QUESTION, chat_history=RECENT_TURN)

    sent_system = model.seen[-1][0]
    assert sent_system.content == [{"type": "text", "text": STABLE}, {"type": "text", "text": VOLATILE}]
    assert sent_system.additional_kwargs == system_message.additional_kwargs


@pytest.mark.parametrize(
    "cache_style,marked_stable_blocks",
    [
        ("anthropic", [{"type": "text", "text": STABLE, "cache_control": {"type": "ephemeral"}}]),
        ("bedrock_converse", [{"type": "text", "text": STABLE}, {"cachePoint": {"type": "default"}}]),
    ],
)
@pytest.mark.asyncio
async def test_block_system_prompt_keeps_its_cache_marker_on_the_stable_block(cache_style, marked_stable_blocks):
    system_message = build_cacheable_system_message(STABLE, VOLATILE)
    model = RecordingChatModel()
    caching_model = PromptCachingChatModel(inner=model, cache_style=cache_style)
    agent = ReActAgentLC(llm_model=caching_model, system_prompt=system_message, tools=[])

    await agent.invoke(QUESTION, chat_history=[_retrieved(ACME_BLOCK), *RECENT_TURN])

    assert model.seen[-1][0].content == [
        *marked_stable_blocks,
        {"type": "text", "text": VOLATILE},
        {"type": "text", "text": f"\n\n{QUOTED_ACME_BLOCK}"},
    ]
    assert system_message.content == [{"type": "text", "text": STABLE}, {"type": "text", "text": VOLATILE}]


@pytest.mark.asyncio
async def test_one_chat_block_never_leaks_into_the_next_call():
    agent, model = _agent()

    await agent.invoke(QUESTION, chat_history=[_retrieved(ACME_BLOCK), *RECENT_TURN])
    await agent.invoke(QUESTION, chat_history=[_retrieved(GLOBEX_BLOCK), *RECENT_TURN])
    await agent.invoke(QUESTION, chat_history=RECENT_TURN)

    system_prompts = [sent[0].content for sent in model.seen]
    assert system_prompts == [f"{PROMPT}\n\n{QUOTED_ACME_BLOCK}", f"{PROMPT}\n\n{QUOTED_GLOBEX_BLOCK}", PROMPT]
    assert agent.system_prompt == PROMPT


@pytest.mark.asyncio
async def test_block_system_prompt_is_not_changed_between_calls():
    system_message = build_cacheable_system_message(STABLE, VOLATILE)
    agent, model = _agent(system_message)

    await agent.invoke(QUESTION, chat_history=[_retrieved(ACME_BLOCK), *RECENT_TURN])
    await agent.invoke(QUESTION, chat_history=[_retrieved(GLOBEX_BLOCK), *RECENT_TURN])

    last_blocks = [sent[0].content[-1]["text"] for sent in model.seen]
    assert last_blocks == [f"\n\n{QUOTED_ACME_BLOCK}", f"\n\n{QUOTED_GLOBEX_BLOCK}"]
    assert all(len(sent[0].content) == 3 for sent in model.seen)
    assert system_message.content == [{"type": "text", "text": STABLE}, {"type": "text", "text": VOLATILE}]


@pytest.mark.asyncio
async def test_every_model_call_of_a_tool_loop_gets_the_block():
    async def lookup(_inp):
        return "order found"

    tool = BaseTool(node_id="tool-1", name="lookup", description="d", parameters={}, function=lookup)
    model = ToolThenAnswerChatModel()
    agent = ReActAgentLC(llm_model=model, system_prompt=PROMPT, tools=[tool])

    result = await agent.invoke(QUESTION, chat_history=[_retrieved(ACME_BLOCK), *RECENT_TURN])

    assert result["response"] == "the answer"
    assert [tool_use["tool_name"] for tool_use in result["tools_used"]] == ["lookup"]
    assert len(model.seen) == 2
    for sent in model.seen:
        assert sent[0].content == f"{PROMPT}\n\n{QUOTED_ACME_BLOCK}"
        assert not any(isinstance(message, SystemMessage) for message in sent[1:])


@pytest.mark.asyncio
async def test_compacted_summary_reaches_the_model_the_same_way():
    summary_text = InMemoryConversationMemory("chat-acme")._format_compacted_summary(
        {"prose_summary": "The customer asked about an Acme order.", "compacted_message_count": 12}
    )
    summary_entry = {"role": "system", "content": summary_text, "message_type": "compacted_summary"}
    agent, model = _agent()

    await agent.invoke(QUESTION, chat_history=[summary_entry, *RECENT_TURN])

    assert summary_text.startswith("[Conversation History Summary]")
    assert _sent_list(model.seen[-1]) == [
        ("SystemMessage", f"{PROMPT}\n\n{QUOTED_HISTORY_NOTICE}\n\n{summary_text}"),
        *_sent_list(RECENT_TURN_MESSAGES),
        ("HumanMessage", QUESTION),
    ]


@pytest.mark.asyncio
async def test_streamed_reply_gets_the_block_and_still_reports_its_text():
    tokens = []
    model = StreamingChatModel()
    agent = ReActAgentLC(
        llm_model=model, system_prompt=PROMPT, tools=[], on_token=lambda call_id, text: tokens.append(text)
    )

    result = await agent.invoke(QUESTION, chat_history=[_retrieved(ACME_BLOCK), *RECENT_TURN])

    assert tokens == ["the ", "answer"]
    assert result["response"] == "the answer"
    assert _sent_list(model.seen[-1]) == [
        ("SystemMessage", f"{PROMPT}\n\n{QUOTED_ACME_BLOCK}"),
        *_sent_list(RECENT_TURN_MESSAGES),
        ("HumanMessage", QUESTION),
    ]


@pytest.mark.asyncio
async def test_empty_system_prompt_sends_only_the_quoted_block_as_system_content():
    agent, model = _agent("")

    await agent.invoke(QUESTION, chat_history=[_retrieved(ACME_BLOCK), *RECENT_TURN])

    assert _sent_list(model.seen[-1]) == [
        ("SystemMessage", QUOTED_ACME_BLOCK),
        *_sent_list(RECENT_TURN_MESSAGES),
        ("HumanMessage", QUESTION),
    ]


@pytest.mark.asyncio
async def test_empty_system_prompt_without_system_entries_adds_no_notice():
    agent, model = _agent("")

    await agent.invoke(QUESTION, chat_history=RECENT_TURN)

    assert not any(QUOTED_HISTORY_NOTICE in str(message.content) for message in model.seen[-1])
    assert _sent_list(model.seen[-1])[-3:] == [*_sent_list(RECENT_TURN_MESSAGES), ("HumanMessage", QUESTION)]


def test_other_roles_are_converted_as_before():
    agent, _model = _agent()
    history = [
        {"role": "user", "content": "one"},
        {"role": "human", "content": "two"},
        {"role": "assistant", "content": "three"},
        {"role": "ai", "content": "four"},
        {"role": "agent", "content": {"message": "five"}},
        {"role": "tool", "content": "dropped"},
        {"content": "no role"},
        {"role": "system", "content": "   "},
    ]

    converted = agent._convert_chat_history_to_messages(history)

    assert _sent_list(converted) == [
        ("HumanMessage", "one"),
        ("HumanMessage", "two"),
        ("AIMessage", "three"),
        ("AIMessage", "four"),
        ("AIMessage", '{"message": "five"}'),
        ("HumanMessage", "no role"),
    ]
