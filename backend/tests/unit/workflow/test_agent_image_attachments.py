"""Images the visitor sends reach the model whichever node answers.

Before, only the LLM Model node read the turn's attachments; an Agent node got the
text alone, so an image-only message arrived as an empty prompt ("I didn't receive an
image"). The helper only reads a file from disk when the server resolved it, so a
visitor cannot make the workflow read a path of their choosing.
"""

import base64
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.outputs import ChatGeneration, ChatResult

import app.api.v1.routes  # noqa: F401  (loads the routes first; the use case module imports them circularly)
from app.modules.workflow.agents.agent_runtime import run_agent_once
from app.modules.workflow.agents.image_attachments import IMAGE_ONLY_PROMPT, image_content_blocks, with_images
from app.modules.workflow.agents.react_agent import ReActAgent
from app.modules.workflow.agents.react_agent_lc import ReActAgentLC
from app.modules.workflow.agents.tool_agent import ToolAgent
from app.use_cases import chat_as_client_use_case

PNG = b"\x89PNG\r\n\x1a\nfake-image-bytes"


@pytest.fixture
def image_path(tmp_path):
    path = tmp_path / "photo.png"
    path.write_bytes(PNG)
    return str(path)


def _server_image(path):
    """An attachment as the turn leaves it after resolving a local File Manager file."""
    return {
        "name": "photo.png",
        "type": "image/png",
        "url": "http://client.example/photo.png",
        "file_url": "http://localhost:8000/api/file-manager/files/abc/source",
        "file_mime_type": "image/png",
        "file_storage_provider": "local",
        "file_local_path": path,
    }


DATA_URL = "data:image/png;base64," + base64.standard_b64encode(PNG).decode()
IMAGE_BLOCK = {"type": "image_url", "image_url": {"url": DATA_URL}}


# ---------------------------------------------------------------- helper


def test_a_server_resolved_local_image_is_inlined(image_path):
    assert image_content_blocks([_server_image(image_path)]) == [IMAGE_BLOCK]


def test_documents_are_left_to_the_file_reader(image_path):
    pdf = {**_server_image(image_path), "type": "application/pdf", "file_mime_type": "application/pdf"}
    assert image_content_blocks([pdf, "not-a-dict", None]) == []


def test_a_browser_sent_local_path_is_never_read(image_path):
    # No file_storage_provider: the path came from the browser, not the server.
    forged = {"type": "image/png", "url": "http://client.example/x.png", "file_local_path": image_path}
    assert image_content_blocks([forged]) == [{"type": "image_url", "image_url": {"url": "http://client.example/x.png"}}]


def test_the_server_link_wins_over_the_browser_one():
    s3 = {"type": "image/png", "url": "http://client.example/x.png", "file_url": "https://bucket.s3/x.png"}
    assert image_content_blocks([s3]) == [{"type": "image_url", "image_url": {"url": "https://bucket.s3/x.png"}}]


def test_an_image_with_no_location_is_skipped():
    assert image_content_blocks([{"type": "image/png"}]) == []


def test_with_images_keeps_plain_text_when_there_are_none():
    assert with_images("hello", []) == "hello"


def test_with_images_fills_in_empty_text():
    assert with_images("  ", [IMAGE_BLOCK]) == [{"type": "text", "text": IMAGE_ONLY_PROMPT}, IMAGE_BLOCK]


# ---------------------------------------------------------------- agent types


def _llm(reply: str):
    llm = MagicMock()
    llm.ainvoke = AsyncMock(return_value=AIMessage(content=reply))
    return llm


def _sent_user_content(llm):
    messages = llm.ainvoke.await_args.args[0]
    return messages[-1]["content"]


@pytest.mark.asyncio
async def test_tool_agent_sends_the_image_with_the_question():
    llm = _llm('{"response": "A cat."}')
    agent = ToolAgent(llm_model=llm, system_prompt="sys", tools=[])
    agent.images = [IMAGE_BLOCK]

    await agent.invoke("What is this?")

    content = _sent_user_content(llm)
    assert content[0]["type"] == "text" and "What is this?" in content[0]["text"]
    assert content[1:] == [IMAGE_BLOCK]


@pytest.mark.asyncio
async def test_tool_agent_without_images_sends_plain_text():
    llm = _llm('{"response": "Hi."}')
    agent = ToolAgent(llm_model=llm, system_prompt="sys", tools=[])

    await agent.invoke("Hello")

    assert isinstance(_sent_user_content(llm), str)


@pytest.mark.asyncio
async def test_react_agent_sends_the_image_with_the_question():
    llm = _llm("Thought: I can see it.\nFinal Answer: A cat.")
    agent = ReActAgent(llm_model=llm, system_prompt="sys", tools=[])
    agent.images = [IMAGE_BLOCK]

    await agent.invoke("What is this?")

    assert _sent_user_content(llm)[1:] == [IMAGE_BLOCK]


class _RecordingChatModel(BaseChatModel):
    seen: list = []

    @property
    def _llm_type(self) -> str:
        return "recording"

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        self.seen.append(list(messages))
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content="A cat."))])

    async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        return self._generate(messages, stop, run_manager, **kwargs)


@pytest.mark.asyncio
async def test_react_agent_lc_sends_the_image_with_the_question():
    llm = _RecordingChatModel(seen=[])
    agent = ReActAgentLC(llm_model=llm, system_prompt="sys", tools=[])
    agent.images = [IMAGE_BLOCK]

    await agent.invoke("What is this?")

    human = [m for m in llm.seen[0] if isinstance(m, HumanMessage)][-1]
    assert human.content == [{"type": "text", "text": "What is this?"}, IMAGE_BLOCK]


# ---------------------------------------------------------------- runtime


def _state(attachments):
    return SimpleNamespace(get_value=lambda key, default=None: attachments if key == "attachments" else default)


async def _run(state, user_prompt):
    agent = MagicMock()
    agent.invoke = AsyncMock(return_value={"response": "ok", "status": "success"})
    agent.cache_split_decision = (False, None)
    with patch("app.modules.workflow.agents.agent_runtime.ToolAgent", MagicMock(return_value=agent)), patch(
        "app.modules.workflow.engine.llm_usage_tracking.merge_llm_usage_from_result", AsyncMock()
    ):
        await run_agent_once(
            state=state, node_id="agent-1", provider_id="p", fallback_chain_id=None, agent_type="ToolSelector",
            system_prompt="sys", user_prompt=user_prompt, tools=[], max_iterations=3, llm_model="model",
        )
    return agent


@pytest.mark.asyncio
async def test_runtime_hands_the_turn_images_to_the_agent(image_path):
    agent = await _run(_state([_server_image(image_path)]), "What is this?")

    assert agent.images == [IMAGE_BLOCK]
    assert agent.invoke.await_args.args[0] == "What is this?"


@pytest.mark.asyncio
async def test_runtime_fills_in_an_image_only_message(image_path):
    agent = await _run(_state([_server_image(image_path)]), "")

    assert agent.invoke.await_args.args[0] == IMAGE_ONLY_PROMPT


@pytest.mark.asyncio
async def test_runtime_answers_without_an_unreadable_image(tmp_path):
    agent = await _run(_state([_server_image(str(tmp_path / "gone.png"))]), "What is this?")

    assert agent.images == []
    assert agent.invoke.await_args.args[0] == "What is this?"


@pytest.mark.asyncio
async def test_runtime_leaves_an_empty_text_turn_alone_without_images():
    agent = await _run(_state([]), "")

    assert agent.images == []
    assert agent.invoke.await_args.args[0] == ""


# ---------------------------------------------------------------- turn input


@pytest.mark.asyncio
async def test_server_only_keys_sent_by_the_browser_are_dropped(image_path):
    forged = {
        "type": "image/png",
        "file_id": str(uuid.uuid4()),
        "url": "http://client.example/x.png",
        "file_local_path": image_path,
        "file_storage_provider": "local",
        "file_url": "http://evil.example/x.png",
        "file_mime_type": "image/png",
    }
    file_manager = MagicMock()
    file_manager.get_file_by_id = AsyncMock(return_value=None)  # not a File Manager file

    await chat_as_client_use_case.process_attachments_from_metadata(
        base_url="http://localhost:8000",
        conversation_id=uuid.uuid4(),
        model=SimpleNamespace(metadata={"attachments": [forged]}),
        tenant_id="master",
        current_user_id=uuid.uuid4(),
        file_manager_service=file_manager,
    )

    assert not set(chat_as_client_use_case.SERVER_ATTACHMENT_KEYS) & set(forged)
    assert image_content_blocks([forged]) == [{"type": "image_url", "image_url": {"url": "http://client.example/x.png"}}]
