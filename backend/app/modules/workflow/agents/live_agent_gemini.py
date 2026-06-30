"""
Native speech-to-speech agent over the Gemini Live API.

The Gemini Live counterpart to the text agents in this package (e.g.
`ReActAgentLC`): it holds a system prompt + workflow tools and talks to the
model directly — a single multimodal model hears the user's audio, calls tools
natively, and answers in audio — so there is no LangChain LLM / ReAct loop.

Two entry points mirror the agent contract:
  - `invoke()`  — one record/send turn: send one input, collect the full reply,
                  return `{transcript, message, audio, steps}`.
  - `stream()`  — a continuous bidirectional call: mic PCM in, reply audio out,
                  plus transcript/turn events over callbacks.

Audio primitives (the `LiveConnectConfig` builder, PCM conversion, providers)
live in `app.modules.workflow.audio`; this class only orchestrates the session.
Tool execution and turn persistence are injected as async callbacks so the agent
stays transport-agnostic; absent an override it executes its own `tools`.
"""

import asyncio
import logging
from typing import Any, Awaitable, Callable, Dict, List, Optional

from app.modules.workflow.agents.base_tool import BaseTool
from app.modules.workflow.audio.gemini_live import (
    DEFAULT_LIVE_MODEL,
    execute_workflow_tool,
)

logger = logging.getLogger(__name__)

# Gemini Live expects 16 kHz mono PCM in; emits 24 kHz mono PCM out.
LIVE_INPUT_MIME = "audio/pcm;rate=16000"

SendAudio = Callable[[bytes], Awaitable[None]]
SendEvent = Callable[[Dict[str, Any]], Awaitable[None]]
# (user_transcript) -> None — make the live transcript available to engine tools
OnTranscript = Callable[[str], Awaitable[None]]
# (user_text, agent_text, tool_steps) -> None
PersistTurn = Callable[[str, str, List[Dict[str, Any]]], Awaitable[None]]


async def _noop_event(_event: Dict[str, Any]) -> None:
    """Event sink for the single-turn path, which collects instead of streaming."""
    return None


class GeminiLiveAgent:
    """Bidirectional Gemini Live voice agent.

    Holds the agent's `tools` (already PII-wrapped by the caller if needed) and an
    already-assembled `LiveConnectConfig`, and executes those tools itself via the
    shared workflow runner — one tool path for both entry points. Before running a
    turn's tools it invokes the optional `on_transcript` callback so engine-bound
    tools templating `{{session.message}}` see the live user transcript.
    """

    def __init__(
        self,
        *,
        api_key: str,
        model: Optional[str],
        live_config: Dict[str, Any],
        tools: Optional[List[BaseTool]] = None,
        max_tool_calls: int = 10,
        on_transcript: Optional[OnTranscript] = None,
        persist_turn: Optional[PersistTurn] = None,
    ) -> None:
        self._api_key = api_key
        self._model = model or DEFAULT_LIVE_MODEL
        self._live_config = live_config
        self._tools = tools or []
        self._max_tool_calls = max_tool_calls
        self._on_transcript = on_transcript
        self._persist_turn = persist_turn
        self._user_tx: List[str] = []
        self._agent_tx: List[str] = []
        self._tool_steps: List[Dict[str, Any]] = []  # tool calls made this turn

    # ==================== ENTRY POINTS ====================

    async def invoke(
        self, *, pcm_input: Optional[bytes] = None, text_input: Optional[str] = None
    ) -> Dict[str, Any]:
        """Run one turn: send a single input, collect the whole reply, return it.

        The single-shot counterpart to `stream()` (record/send path). Buffers the
        reply instead of streaming it and returns
        `{transcript, message, audio (raw 24 kHz PCM), steps}`. Tool calls and
        message parsing reuse the same logic as the streaming path.
        """
        from google import genai
        from google.genai import types

        self._log_session("single-turn")
        audio_out = bytearray()

        async def _collect_audio(chunk: bytes) -> None:
            audio_out.extend(chunk)

        client = genai.Client(api_key=self._api_key)
        async with client.aio.live.connect(model=self._model, config=self._live_config) as session:
            if pcm_input is not None:
                await session.send_realtime_input(
                    audio=types.Blob(data=pcm_input, mime_type=LIVE_INPUT_MIME)
                )
                await session.send_realtime_input(audio_stream_end=True)
            else:
                # Native-audio models require realtime input for text too.
                await session.send_realtime_input(text=text_input or "")

            async for message in session.receive():
                if await self._consume_message(session, message, _collect_audio, _noop_event):
                    break

        return {
            "transcript": "".join(self._user_tx).strip() or None,
            "message": "".join(self._agent_tx).strip(),
            "audio": bytes(audio_out),
            "steps": list(self._tool_steps),
        }

    async def stream(self, audio_in: asyncio.Queue, send_audio: SendAudio, send_event: SendEvent) -> None:
        """Hold a continuous call: stream mic PCM up, reply audio + events down."""
        from google import genai

        self._log_session("streaming")
        client = genai.Client(api_key=self._api_key)
        async with client.aio.live.connect(model=self._model, config=self._live_config) as session:
            await send_event({"type": "ready"})
            await asyncio.gather(
                self._pump_client_audio(session, audio_in),
                self._pump_model_events(session, send_audio, send_event),
            )

    # ==================== SESSION INTERNALS ====================

    def _log_session(self, kind: str) -> None:
        """Log the model + non-secret config keys when opening a session."""
        logger.debug(
            "Gemini Live %s session: model=%s, config=%s",
            kind,
            self._model,
            {k: v for k, v in self._live_config.items() if k != "system_instruction"},
        )

    async def _pump_client_audio(self, session: Any, audio_in: asyncio.Queue) -> None:
        """Forward client mic PCM to Gemini (server VAD owns turn boundaries)."""
        from google.genai import types

        while True:
            chunk = await audio_in.get()
            if chunk is None:  # client disconnected
                return
            await session.send_realtime_input(
                audio=types.Blob(data=chunk, mime_type=LIVE_INPUT_MIME)
            )

    async def _pump_model_events(self, session: Any, send_audio: SendAudio, send_event: SendEvent) -> None:
        """Stream Gemini output (audio, transcripts, tool calls) to the client.

        `session.receive()` yields one turn's messages and then the async
        generator completes; re-enter it for each subsequent turn so multi-turn
        conversations keep responding. If it returns without yielding anything,
        the session is closing and we stop.
        """
        while True:
            received_any = False
            async for message in session.receive():
                received_any = True
                if await self._consume_message(session, message, send_audio, send_event):
                    await self._finalize_turn(send_event)

            if not received_any:
                # Generator returned without yielding -> session is closing.
                return

    async def _consume_message(
        self, session: Any, message: Any, send_audio: SendAudio, send_event: SendEvent
    ) -> bool:
        """Handle one received message; return True when the model turn completed.

        Shared by `stream()` and `invoke()`: tool calls, transcripts (buffered +
        emitted), audio (streamed or collected via `send_audio`), and barge-in.
        Transcript/event emission is a no-op on the single-turn path.
        """
        if message.tool_call and message.tool_call.function_calls:
            await self._handle_tool_calls(session, message.tool_call.function_calls, send_event)
            return False

        content = message.server_content
        if not content:
            return False

        if content.input_transcription and content.input_transcription.text:
            text = content.input_transcription.text
            self._user_tx.append(text)
            await send_event({"type": "input_transcript", "text": text})

        if content.output_transcription and content.output_transcription.text:
            text = content.output_transcription.text
            self._agent_tx.append(text)
            await send_event({"type": "output_transcript", "text": text})

        if content.model_turn:
            for part in content.model_turn.parts or []:
                if part.inline_data and part.inline_data.data:
                    await send_audio(bytes(part.inline_data.data))

        if getattr(content, "interrupted", False):
            self._agent_tx.clear()
            await send_event({"type": "interrupted"})

        return bool(content.turn_complete)

    async def _handle_tool_calls(self, session: Any, function_calls: List[Any], send_event: SendEvent) -> None:
        """Execute the model's tool calls and return the results to the session.

        `execute_workflow_tool` already validates args and turns failures into an
        `{"error": ...}` payload, so one tool's failure never kills the turn.
        """
        from google.genai import types

        # Surface the live user transcript to engine-bound tools before running
        # them (the node sets it on the workflow state behind this callback).
        if self._on_transcript:
            transcript = "".join(self._user_tx).strip()
            if transcript:
                await self._on_transcript(transcript)

        responses = []
        for call in function_calls:
            if self._max_tool_calls <= 0:
                responses.append(
                    types.FunctionResponse(
                        id=call.id, name=call.name, response={"error": "Tool call limit reached"}
                    )
                )
                continue
            self._max_tool_calls -= 1
            args = dict(call.args or {})
            result = await execute_workflow_tool(self._tools, call.name, args)
            self._tool_steps.append({"tool": call.name, "input": args, "output": result})
            await send_event({"type": "tool_call", "name": call.name})
            responses.append(
                types.FunctionResponse(id=call.id, name=call.name, response={"result": result})
            )
        await session.send_tool_response(function_responses=responses)

    async def _finalize_turn(self, send_event: SendEvent) -> None:
        user_text = "".join(self._user_tx).strip()
        agent_text = "".join(self._agent_tx).strip()
        steps = list(self._tool_steps)
        if self._persist_turn and (user_text or agent_text):
            # Persist in the background so transcript saving / tone analysis
            # latency never delays the next spoken turn.
            asyncio.create_task(self._safe_persist(user_text, agent_text, steps))
        await send_event(
            {"type": "turn_complete", "transcript": user_text, "response": agent_text}
        )
        self._user_tx = []
        self._agent_tx = []
        self._tool_steps = []

    async def _safe_persist(self, user_text: str, agent_text: str, steps: List[Dict[str, Any]]) -> None:
        try:
            await self._persist_turn(user_text, agent_text, steps)
        except Exception:  # persistence is best-effort
            logger.exception("Live voice: failed to persist turn")
