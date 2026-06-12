"""Unit tests for VoiceAgentNode (native speech-to-speech via Gemini Live API)."""

import base64
from types import SimpleNamespace
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.modules.workflow.audio.audio_input import pcm_to_wav
from app.modules.workflow.engine.nodes.voice_agent_node import (
    VoiceAgentNode,
    _history_to_live_turns,
    _tool_declarations,
)
from app.modules.workflow.engine.workflow_engine import _sanitize_output_for_memory

_PCM_16K = b"\x00\x01" * 1600  # 0.1s of 16 kHz s16 mono
_WAV_16K = pcm_to_wav(_PCM_16K, rate=16000)
_WAV_B64 = base64.b64encode(_WAV_16K).decode("utf-8")
_PCM_OUT = b"\x02\x03" * 2400  # model reply audio (24 kHz PCM)


class _FakeState:
    def __init__(self, values: Dict[str, Any] | None = None):
        self.initial_values: Dict[str, Any] = {"message": "[Voice message]"}
        self._values = values or {}

    def get_value(self, key_path: str, default: Any = None) -> Any:
        return self._values.get(key_path, default)


class _FakeTool:
    """Mimics the workflow BaseTool (app/modules/workflow/agents/base_tool.py)."""

    name = "get_weather"
    description = "Get the weather for a city"
    parameters = {
        "city": {"type": "string", "description": "City name", "required": True},
    }
    return_direct = False

    def __init__(self):
        self.calls: List[Dict[str, Any]] = []

    async def invoke(self, **kwargs):
        self.calls.append(kwargs)
        return {"temp": "21C"}


class _FakeSession:
    def __init__(self, messages: List[Any]):
        self._messages = messages
        self.client_content_calls: List[Any] = []
        self.realtime_calls: List[Dict[str, Any]] = []
        self.tool_response_calls: List[Any] = []

    async def send_client_content(self, turns=None, turn_complete=True):
        self.client_content_calls.append({"turns": turns, "turn_complete": turn_complete})

    async def send_realtime_input(self, **kwargs):
        self.realtime_calls.append(kwargs)

    async def send_tool_response(self, function_responses=None):
        self.tool_response_calls.append(function_responses)

    async def receive(self):
        for message in self._messages:
            yield message


class _FakeConnectContext:
    def __init__(self, session: _FakeSession):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, *args):
        return False


def _msg(
    tool_calls: List[Any] | None = None,
    input_tx: str | None = None,
    output_tx: str | None = None,
    audio: bytes | None = None,
    turn_complete: bool = False,
) -> SimpleNamespace:
    server_content = None
    if input_tx is not None or output_tx is not None or audio is not None or turn_complete:
        server_content = SimpleNamespace(
            input_transcription=SimpleNamespace(text=input_tx) if input_tx else None,
            output_transcription=SimpleNamespace(text=output_tx) if output_tx else None,
            model_turn=SimpleNamespace(
                parts=[SimpleNamespace(inline_data=SimpleNamespace(data=audio))]
            )
            if audio
            else None,
            turn_complete=turn_complete,
        )
    tool_call = SimpleNamespace(function_calls=tool_calls) if tool_calls else None
    return SimpleNamespace(tool_call=tool_call, server_content=server_content)


def _make_node(
    source_output: Any = None,
    state: _FakeState | None = None,
    tools: List[Any] | None = None,
) -> VoiceAgentNode:
    node = object.__new__(VoiceAgentNode)
    node.node_id = "voice-agent-1"
    node._pii_prompt_token_items = []
    node._pii_history_token_items = []
    node_state = state or _FakeState()
    node.get_state = lambda: node_state
    node.get_input_from_source = lambda: source_output
    node.get_connected_nodes = lambda tag: tools or []
    node.get_memory = lambda: None
    node.set_node_input = lambda data: None
    return node


def _native_config(**overrides: Any) -> Dict[str, Any]:
    config = {
        "voiceProviderId": "voice-provider-id",
        "model": "gemini-3.1-flash-live-preview",
        "voice": "Kore",
        "systemPrompt": "Be helpful.",
        "userPrompt": "typed question",
    }
    config.update(overrides)
    return config


def _audio_source_output() -> Dict[str, Any]:
    return {
        "message": "[Voice message]",
        "audio_data": {
            "type": "audio",
            "data": _WAV_B64,
            "encoding": "base64",
            "format": "wav",
        },
    }


def _patch_provider(provider_type: str = "gemini"):
    return patch(
        "app.modules.workflow.audio.provider.load_connection_data",
        AsyncMock(return_value=(provider_type, {"api_key": "test-key"})),
    )


def _patch_client(session: _FakeSession):
    fake_client = MagicMock()
    fake_client.aio.live.connect = MagicMock(return_value=_FakeConnectContext(session))
    return patch("google.genai.Client", MagicMock(return_value=fake_client))


@pytest.mark.asyncio
class TestNativeVoiceFlow:
    async def test_voice_in_voice_out_with_tool_call(self):
        tool = _FakeTool()
        state = _FakeState()
        node = _make_node(source_output=_audio_source_output(), state=state, tools=[tool])
        session = _FakeSession([
            _msg(tool_calls=[SimpleNamespace(id="fc1", name="get_weather", args={"city": "Berlin"})]),
            _msg(input_tx="what's the weather in Berlin?"),
            _msg(output_tx="It is 21 degrees.", audio=_PCM_OUT),
            _msg(turn_complete=True),
        ])

        with _patch_provider(), _patch_client(session):
            output = await node.process(_native_config())

        # Audio was sent as 16 kHz PCM realtime input + stream end
        assert session.realtime_calls[0]["audio"].data == _PCM_16K
        assert session.realtime_calls[0]["audio"].mime_type == "audio/pcm;rate=16000"
        assert session.realtime_calls[1] == {"audio_stream_end": True}
        # Tool was executed natively and a response was sent back
        assert tool.calls == [{"city": "Berlin"}]
        assert len(session.tool_response_calls) == 1
        assert session.tool_response_calls[0][0].name == "get_weather"
        # Output shape
        assert output["message"] == "It is 21 degrees."
        assert output["transcript"] == "what's the weather in Berlin?"
        assert output["steps"] == [
            {"tool": "get_weather", "input": {"city": "Berlin"}, "output": {"temp": "21C"}}
        ]
        wav_out = base64.b64decode(output["audio"]["data"])
        assert wav_out[:4] == b"RIFF"
        assert output["audio"]["format"] == "wav"
        # Memory user-side fix uses the input transcription
        assert state.initial_values["message"] == "what's the weather in Berlin?"

    async def test_text_fallback_uses_realtime_text_input(self):
        node = _make_node(source_output={"message": "typed question"})
        session = _FakeSession([
            _msg(output_tx="answer", audio=_PCM_OUT),
            _msg(turn_complete=True),
        ])

        with _patch_provider(), _patch_client(session):
            output = await node.process(_native_config())

        # Native-audio models require realtime input (client_content is
        # rejected mid-session with 1007 INVALID_ARGUMENT)
        assert session.client_content_calls == []
        assert session.realtime_calls == [{"text": "typed question"}]
        assert output["message"] == "answer"
        assert "transcript" not in output
        assert "audio" in output

    async def test_history_replayed_in_system_instruction(self):
        node = _make_node(source_output={"message": "typed question"})
        node._get_chat_history_for_agent = AsyncMock(
            return_value=[
                {"role": "user", "content": "hi"},
                {"role": "assistant", "content": {"message": "hello"}},
            ]
        )
        session = _FakeSession([_msg(output_tx="answer", turn_complete=True)])

        fake_client = MagicMock()
        fake_client.aio.live.connect = MagicMock(return_value=_FakeConnectContext(session))
        with _patch_provider(), patch("google.genai.Client", MagicMock(return_value=fake_client)):
            await node.process(_native_config(memory=True))

        # History goes into the system instruction, never via client_content
        assert session.client_content_calls == []
        live_config = fake_client.aio.live.connect.call_args.kwargs["config"]
        assert "User: hi" in live_config["system_instruction"]
        assert "Assistant: hello" in live_config["system_instruction"]


@pytest.mark.asyncio
class TestErrorHandling:
    async def test_missing_voice_provider(self):
        node = _make_node(source_output=_audio_source_output())
        output = await node.process(_native_config(voiceProviderId=None))
        assert "error" in output

    async def test_non_gemini_provider_rejected(self):
        node = _make_node(source_output=_audio_source_output())
        with _patch_provider(provider_type="openai"):
            output = await node.process(_native_config())
        assert "error" in output
        assert "Gemini" in output["message"]

    async def test_compressed_audio_rejected(self):
        webm_payload = base64.b64encode(b"x" * 200).decode("utf-8")
        node = _make_node(
            source_output={
                "audio_data": {
                    "type": "audio",
                    "data": webm_payload,
                    "encoding": "base64",
                    "format": "webm",
                }
            }
        )
        with _patch_provider():
            output = await node.process(_native_config())
        assert "error" in output
        assert "webm" in output["error"]

    async def test_live_session_failure_returns_error(self):
        node = _make_node(source_output=_audio_source_output())
        fake_client = MagicMock()
        fake_client.aio.live.connect = MagicMock(side_effect=RuntimeError("connection refused"))
        with _patch_provider(), patch("google.genai.Client", MagicMock(return_value=fake_client)):
            output = await node.process(_native_config())
        assert "error" in output
        assert "connection refused" in output["error"]

    async def test_tool_call_limit_enforced(self):
        tool = _FakeTool()
        node = _make_node(source_output=_audio_source_output(), tools=[tool])
        session = _FakeSession([
            _msg(tool_calls=[SimpleNamespace(id="fc1", name="get_weather", args={"city": "Rome"})]),
            _msg(tool_calls=[SimpleNamespace(id="fc2", name="get_weather", args={"city": "Oslo"})]),
            _msg(output_tx="done", turn_complete=True),
        ])

        with _patch_provider(), _patch_client(session):
            output = await node.process(_native_config(maxToolCalls=1))

        assert len(tool.calls) == 1
        assert len(output["steps"]) == 1
        # Second call answered with the limit error instead of execution
        assert session.tool_response_calls[1][0].response == {"error": "Tool call limit reached"}


class TestAudioResolution:
    def test_audio_from_state_audio_data_key(self):
        # Mirrors the /test-node path: the dialog injects audio under the
        # `audio_data` state key, with no connected source node.
        state = _FakeState(values={
            "audio_data": {
                "type": "audio", "data": _WAV_B64, "encoding": "base64", "format": "wav",
            }
        })
        node = _make_node(source_output=None, state=state)
        audio_bytes, audio_format = node._get_input_audio({})
        assert audio_bytes == _WAV_16K
        assert audio_format == "wav"

    def test_no_audio_returns_none(self):
        node = _make_node(source_output=None, state=_FakeState())
        assert node._get_input_audio({}) == (None, "")


class TestHelpers:
    def test_tool_declarations(self):
        declarations = _tool_declarations([_FakeTool()])
        assert declarations == [
            {
                "name": "get_weather",
                "description": "Get the weather for a city",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "city": {"type": "string", "description": "City name"},
                    },
                    "required": ["city"],
                },
            }
        ]

    def test_history_to_live_turns_skips_empty_and_maps_roles(self):
        turns = _history_to_live_turns([
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": ""},
            {"role": "ai", "content": {"message": "hello"}},
        ])
        assert turns == [
            {"role": "user", "parts": [{"text": "hi"}]},
            {"role": "model", "parts": [{"text": "hello"}]},
        ]


class TestSanitizeOutputForMemory:
    def test_strips_nested_audio_payload(self):
        output = {
            "message": "answer",
            "steps": [],
            "audio": {"type": "audio", "data": "AAAA", "encoding": "base64", "format": "wav"},
        }
        sanitized = _sanitize_output_for_memory(output)
        assert "audio" not in sanitized
        assert sanitized["message"] == "answer"

    def test_keeps_bare_audio_dict(self):
        tts_output = {"type": "audio", "data": "AAAA", "encoding": "base64", "format": "mp3"}
        assert _sanitize_output_for_memory(tts_output) == tts_output

    def test_passthrough_for_strings(self):
        assert _sanitize_output_for_memory("plain text") == "plain text"
