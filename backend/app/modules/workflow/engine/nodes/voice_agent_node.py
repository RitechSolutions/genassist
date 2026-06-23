"""
Voice Agent node: native speech-to-speech via the Gemini Live API.

A single multimodal model hears the user's audio, calls connected workflow
tools natively, and answers in audio — text transcripts of both sides are
collected for conversation memory and the chat UI.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from app.modules.workflow.audio.audio_input import (
    build_audio_payload,
    extract_audio_input,
    pcm_to_wav,
    wav_to_pcm16k,
)
from app.modules.workflow.audio.gemini_live import (
    build_live_config,
    explain_live_error,
    history_text,
    history_to_live_turns,
)
from app.modules.workflow.engine.nodes.agent_node import AgentNode

logger = logging.getLogger(__name__)

GEMINI_PROVIDER_TYPE = "gemini"
# Hard ceiling for one turn (history replay + tool calls + audio generation).
TURN_TIMEOUT_SECONDS = 180


def _error(message: str, detail: str) -> Dict[str, Any]:
    """Build the standard user-facing error result for the voice agent."""
    return {"message": message, "error": detail}


class VoiceAgentNode(AgentNode):
    """Native voice agent: audio in -> Gemini Live (reasoning + tool calling) -> audio out.

    Subclasses AgentNode to reuse the tools handle, conversation-memory
    trimming modes (message_count / rag_retrieval) and PII history masking;
    the Live model replaces the text LLM + agent loop entirely, so the
    AgentNode `process` is fully overridden.
    """

    async def process(self, config: Dict[str, Any]) -> Dict[str, Any]:
        # Live-voice "full workflow per turn": the persistent Gemini Live session
        # (held by the live endpoint) already produced this turn's reply, then runs
        # the full DAG for side-effect nodes with the result injected as
        # `live_result`. Surface it instead of opening a new Live turn — so there's
        # no double Gemini call / double tool execution.
        live_result = self.get_state().get_value("live_result")
        if live_result:
            return live_result

        api_key, error = await self._resolve_api_key(config)
        if error:
            return error

        pcm_input, error = self._prepare_audio_input(config)
        if error:
            return error

        system_prompt = config.get("systemPrompt") or "You are a helpful voice assistant."
        user_prompt = config.get("userPrompt", "")

        tools = self.get_connected_nodes("tools") or []
        if config.get("piiMasking") and tools:
            self._wrap_tools_for_pii_unmask(tools)

        history_turns = await self._build_history_turns(config, system_prompt, user_prompt)
        if history_turns:
            # Native-audio Live models reject send_client_content mid-session
            # (1007 INVALID_ARGUMENT) and the installed SDK lacks
            # initial_history_in_client_content, so conversation history is
            # replayed inside the system instruction instead.
            system_prompt = (
                f"{system_prompt}\n\n# Conversation so far\n"
                f"{history_text(history_turns)}\n\n"
                "Continue the conversation naturally from here."
            )

        self.set_node_input({
            "system_prompt": system_prompt,
            "prompt": "[voice message]" if pcm_input else user_prompt,
            "tools_reference": tools,
        })

        try:
            result = await asyncio.wait_for(
                self._run_turn(
                    api_key=api_key,
                    config=config,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    pcm_input=pcm_input,
                    tools=tools,
                ),
                timeout=TURN_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            logger.error("Voice agent Live API turn timed out")
            return _error(
                "The voice agent took too long to respond. Please try again.",
                "Live API turn timeout",
            )
        except Exception as e:
            logger.exception("Error processing voice agent node")
            detail = explain_live_error(str(e))
            return _error(f"The voice agent could not complete your request: {detail}", detail)

        transcript = result.get("transcript")
        if transcript:
            # The engine persists initial_values["message"] (e.g. "[Voice
            # message]") to conversation memory after the run; replace it
            # with what the user actually said.
            self.get_state().initial_values["message"] = transcript

        return result

    async def _resolve_api_key(
        self, config: Dict[str, Any]
    ) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
        """Resolve the Gemini API key from the configured voice provider.

        Returns (api_key, None) on success or (None, error_result) on failure.
        """
        provider_id = config.get("voiceProviderId")
        if not provider_id:
            return None, _error(
                "No voice provider configured for Voice Agent node", "Missing voiceProviderId"
            )

        from app.modules.workflow.audio.provider import load_connection_data

        provider_type, connection_data = await load_connection_data(provider_id)
        if provider_type != GEMINI_PROVIDER_TYPE:
            return None, _error(
                "The Voice Agent requires a Gemini audio provider",
                f"Unsupported voice provider type: {provider_type}",
            )
        api_key = connection_data.get("api_key")
        if not api_key:
            return None, _error(
                "The configured Gemini provider has no API key",
                "Missing api_key in voice provider connection data",
            )
        return api_key, None

    def _prepare_audio_input(
        self, config: Dict[str, Any]
    ) -> Tuple[Optional[bytes], Optional[Dict[str, Any]]]:
        """Locate and convert input audio to Live API PCM.

        Returns (pcm_bytes_or_None, None) on success or (None, error_result) on
        a conversion failure. Absent audio (text turn) yields (None, None).
        """
        audio_bytes, audio_format = self._get_input_audio(config)
        if not audio_bytes:
            return None, None
        try:
            return wav_to_pcm16k(audio_bytes, audio_format), None
        except Exception as e:
            logger.error("Voice agent audio conversion failed: %s", e, exc_info=True)
            return None, _error(
                "Could not process the audio message. Please try again.", str(e)
            )

    async def _build_history_turns(
        self, config: Dict[str, Any], system_prompt: str, user_prompt: str
    ) -> List[Dict[str, Any]]:
        """Fetch and convert conversation memory into Live API content turns."""
        if not config.get("memory"):
            return []
        history = await self._get_chat_history_for_agent(
            self.get_memory(), config, config.get("voiceProviderId"), system_prompt, user_prompt
        )
        return history_to_live_turns(history)

    async def _run_turn(
        self,
        api_key: str,
        config: Dict[str, Any],
        system_prompt: str,
        user_prompt: str,
        pcm_input: Optional[bytes],
        tools: List[Any],
    ) -> Dict[str, Any]:
        """Run one record/send turn through the shared `GeminiLiveAgent`.

        Same Gemini Live engine as the persistent live call, driven single-shot
        via `invoke()`: feed one input, collect the full reply. The agent executes
        its own `tools` here (no override needed — record/send has no live
        transcript to inject). `system_prompt` already has any replayed history
        folded in by `process`.
        """
        from app.modules.workflow.agents.live_agent_gemini import GeminiLiveAgent

        live_config = build_live_config(config, system_prompt=system_prompt, tools=tools)

        agent = GeminiLiveAgent(
            api_key=api_key,
            model=config.get("model"),
            live_config=live_config,
            tools=tools,
            max_tool_calls=int(config.get("maxToolCalls", 10)),
        )
        result = await agent.invoke(pcm_input=pcm_input, text_input=user_prompt)

        output: Dict[str, Any] = {
            "message": result["message"] or "[Audio response]",
            "steps": result["steps"],
        }
        if result.get("transcript"):
            output["transcript"] = result["transcript"]
        if result.get("audio"):
            output["audio"] = build_audio_payload(pcm_to_wav(result["audio"]), "wav")
        return output

    def _get_input_audio(self, config: Dict[str, Any]) -> Tuple[Optional[bytes], str]:
        """Locate input audio, in priority order: explicit config -> source node
        output -> session state. Returns (bytes_or_None, format)."""
        audio_source = config.get("audio_source")
        candidates = [
            audio_source if audio_source not in (None, "null", "None") else None,
            self.get_input_from_source(),
            self._state_audio_payload(),
        ]
        for candidate in candidates:
            if candidate is None:
                continue
            audio_bytes, audio_format = extract_audio_input(candidate)
            if audio_bytes:
                return audio_bytes, audio_format
        return None, ""

    def _state_audio_payload(self) -> Optional[Dict[str, Any]]:
        """Build an audio payload from raw session-state audio data, if present."""
        state_audio = self.get_state().get_value("audio_data")
        if not state_audio:
            return None
        if isinstance(state_audio, dict):
            return state_audio
        return {
            "type": "audio",
            "data": state_audio,
            "encoding": "base64",
            "format": self.get_state().get_value("audio_format") or "wav",
        }

    # ------------------------------------------------------------------
    # Persistent live session support.
    #
    # The live voice endpoint holds one long-lived Gemini Live session (via
    # `GeminiLiveAgent`) outside the per-message DAG run. These methods let it
    # reuse this node without executing the workflow: materialize the node,
    # build the session config, and execute a connected tool per turn — so the
    # node stays the single source of truth for its config + tools.
    # ------------------------------------------------------------------

    @classmethod
    async def materialize(
        cls, agent_service: Any, agent_id: str, thread_id: str
    ) -> "VoiceAgentNode":
        """Build an agent's single Voice Agent node (+ its connected tools, lazily
        via ``get_connected_nodes``) for a live session — without running the DAG.
        """
        from app.core.exceptions.error_messages import ErrorKey
        from app.core.exceptions.exception_classes import AppException
        from app.modules.workflow.engine.workflow_engine import WorkflowEngine
        from app.modules.workflow.engine.workflow_state import WorkflowState

        agent = await agent_service.get_by_id_full(UUID(agent_id))
        if not getattr(agent, "workflow", None):
            raise AppException(
                status_code=404, error_key=ErrorKey.AGENT_NOT_FOUND,
                error_detail="Agent has no workflow",
            )

        engine = WorkflowEngine(agent.workflow)
        voice_nodes = [n for n in engine.workflow["nodes"] if n.get("type") == "voiceAgentNode"]
        if len(voice_nodes) != 1:
            raise AppException(
                status_code=400, error_key=ErrorKey.MISSING_PARAMETER,
                error_detail=f"Agent must contain exactly one voiceAgentNode (found {len(voice_nodes)})",
            )

        state = WorkflowState(
            workflow=engine.workflow, thread_id=thread_id, initial_values={"message": ""}
        )
        return engine.executable_node(voice_nodes[0]["id"], state)

    async def build_live_session_config(self) -> Dict[str, Any]:
        """Everything the live session needs to open a Gemini Live connection:
        the resolved Gemini key, model, tool-call ceiling, the connected tools
        (PII-wrapped if enabled, since the agent executes them itself), and the
        fully-assembled `LiveConnectConfig` (built by the shared `build_live_config`).
        """
        from app.core.exceptions.error_messages import ErrorKey
        from app.core.exceptions.exception_classes import AppException

        cfg = self.node_data
        api_key, error = await self._resolve_api_key(cfg)
        if error:
            raise AppException(
                status_code=400, error_key=ErrorKey.MISSING_PARAMETER,
                error_detail=error.get("error"),
            )
        tools = self.get_connected_nodes("tools") or []
        if cfg.get("piiMasking") and tools:
            self._wrap_tools_for_pii_unmask(tools)
        system_prompt = cfg.get("systemPrompt") or "You are a helpful voice assistant."
        return {
            "api_key": api_key,
            "model": cfg.get("model"),
            "max_tool_calls": int(cfg.get("maxToolCalls", 10)),
            "tools": tools,
            "live_config": build_live_config(cfg, system_prompt=system_prompt, tools=tools),
        }

    def set_live_transcript(self, transcript: str) -> None:
        """Expose the live user transcript to tools templating ``{{session.message}}``.

        Called once per turn (before its tools run) by the live agent; the agent
        executes the connected tools itself, so this only contributes the
        engine-state piece it can't reach.
        """
        if transcript:
            self.get_state().set_value("session.message", transcript)
