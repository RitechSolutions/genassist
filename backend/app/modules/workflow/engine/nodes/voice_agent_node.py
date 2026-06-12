"""
Voice Agent node: native speech-to-speech via the Gemini Live API.

A single multimodal model hears the user's audio, calls connected workflow
tools natively, and answers in audio — text transcripts of both sides are
collected for conversation memory and the chat UI.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional, Tuple

from app.modules.workflow.audio.audio_input import (
    LIVE_API_INPUT_MIME,
    build_audio_payload,
    extract_audio_input,
    pcm_to_wav,
    wav_to_pcm16k,
)
from app.modules.workflow.engine.nodes.agent_node import AgentNode

logger = logging.getLogger(__name__)

DEFAULT_LIVE_MODEL = "gemini-3.1-flash-live-preview"
GEMINI_PROVIDER_TYPE = "gemini"
DEFAULT_VOICE = "Kore"
# Hard ceiling for one turn (history replay + tool calls + audio generation).
TURN_TIMEOUT_SECONDS = 180


def _error(message: str, detail: str) -> Dict[str, Any]:
    """Build the standard user-facing error result for the voice agent."""
    return {"message": message, "error": detail}


def _explain_live_error(error_message: str) -> str:
    """Append a hint for the Live API's opaque 1007 session-setup rejection."""
    if "1007" in error_message or "invalid argument" in error_message.lower():
        # The Live API closes the websocket with 1007 INVALID_ARGUMENT when the
        # session setup is rejected (wrong/unavailable model name for this API
        # key, or an invalid tool schema).
        return (
            f"{error_message} — the Live API rejected the session setup. Check that "
            "the configured Live model is available for this API key and that "
            "connected tool schemas are valid."
        )
    return error_message


class VoiceAgentNode(AgentNode):
    """Native voice agent: audio in -> Gemini Live (reasoning + tool calling) -> audio out.

    Subclasses AgentNode to reuse the tools handle, conversation-memory
    trimming modes (message_count / rag_retrieval) and PII history masking;
    the Live model replaces the text LLM + agent loop entirely, so the
    AgentNode `process` is fully overridden.
    """

    async def process(self, config: Dict[str, Any]) -> Dict[str, Any]:
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

        self.set_node_input({
            "system_prompt": system_prompt,
            "prompt": "[voice message]" if pcm_input else user_prompt,
            "tools_reference": tools,
        })

        try:
            result = await asyncio.wait_for(
                self._run_live_turn(
                    api_key=api_key,
                    config=config,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    pcm_input=pcm_input,
                    history_turns=history_turns,
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
            detail = _explain_live_error(str(e))
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
        return _history_to_live_turns(history)

    async def _run_live_turn(
        self,
        api_key: str,
        config: Dict[str, Any],
        system_prompt: str,
        user_prompt: str,
        pcm_input: Optional[bytes],
        history_turns: List[Dict[str, Any]],
        tools: List[Any],
    ) -> Dict[str, Any]:
        """Run one conversational turn against the Gemini Live API."""
        from google import genai
        from google.genai import types

        # Native-audio Live models reject send_client_content mid-session
        # (1007 INVALID_ARGUMENT) and the installed SDK lacks
        # initial_history_in_client_content, so conversation history is
        # replayed inside the system instruction instead.
        if history_turns:
            system_prompt = (
                f"{system_prompt}\n\n# Conversation so far\n"
                f"{_history_text(history_turns)}\n\n"
                "Continue the conversation naturally from here."
            )

        live_config: Dict[str, Any] = {
            "response_modalities": ["AUDIO"],
            "system_instruction": system_prompt,
            "speech_config": {
                "voice_config": {
                    "prebuilt_voice_config": {
                        "voice_name": config.get("voice") or DEFAULT_VOICE,
                    }
                }
            },
            "input_audio_transcription": {},
            "output_audio_transcription": {},
        }
        language = config.get("language")
        if language:
            live_config["speech_config"]["language_code"] = language
        declarations = _tool_declarations(tools)
        if declarations:
            live_config["tools"] = [{"function_declarations": declarations}]

        client = genai.Client(api_key=api_key)
        model = config.get("model") or DEFAULT_LIVE_MODEL
        max_tool_calls = int(config.get("maxToolCalls", 10))
        logger.debug(
            "Voice agent Live session: model=%s, tools=%s, config=%s",
            model,
            [d["name"] for d in declarations],
            {k: v for k, v in live_config.items() if k != "system_instruction"},
        )

        audio_out = bytearray()
        input_tx: List[str] = []
        output_tx: List[str] = []
        steps: List[Dict[str, Any]] = []

        async with client.aio.live.connect(model=model, config=live_config) as session:
            if pcm_input is not None:
                await session.send_realtime_input(
                    audio=types.Blob(data=pcm_input, mime_type=LIVE_API_INPUT_MIME)
                )
                await session.send_realtime_input(audio_stream_end=True)
            else:
                # Native-audio models require realtime input for text too
                await session.send_realtime_input(text=user_prompt)

            async for message in session.receive():
                if message.tool_call and message.tool_call.function_calls:
                    await self._handle_tool_calls(
                        session, message.tool_call.function_calls, tools, steps, max_tool_calls
                    )
                    continue

                server_content = message.server_content
                if not server_content:
                    continue
                if server_content.input_transcription and server_content.input_transcription.text:
                    input_tx.append(server_content.input_transcription.text)
                if server_content.output_transcription and server_content.output_transcription.text:
                    output_tx.append(server_content.output_transcription.text)
                if server_content.model_turn:
                    for part in server_content.model_turn.parts or []:
                        if part.inline_data and part.inline_data.data:
                            audio_out.extend(part.inline_data.data)
                if server_content.turn_complete:
                    break

        transcript = "".join(input_tx).strip() or None
        message_text = "".join(output_tx).strip()

        output: Dict[str, Any] = {
            "message": message_text or "[Audio response]",
            "steps": steps,
        }
        if transcript:
            output["transcript"] = transcript
        if audio_out:
            output["audio"] = build_audio_payload(pcm_to_wav(bytes(audio_out)), "wav")
        return output

    async def _handle_tool_calls(
        self,
        session: Any,
        function_calls: List[Any],
        tools: List[Any],
        steps: List[Dict[str, Any]],
        max_tool_calls: int,
    ) -> None:
        """Execute the model's tool calls and send results back to the session."""
        from google.genai import types

        responses = []
        for fc in function_calls:
            if len(steps) >= max_tool_calls:
                responses.append(
                    types.FunctionResponse(
                        id=fc.id, name=fc.name, response={"error": "Tool call limit reached"}
                    )
                )
                continue
            tool_result = await _execute_tool(tools, fc.name, fc.args or {})
            steps.append({"tool": fc.name, "input": fc.args or {}, "output": tool_result})
            responses.append(
                types.FunctionResponse(id=fc.id, name=fc.name, response={"result": tool_result})
            )
        await session.send_tool_response(function_responses=responses)

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


# Workflow tool parameter types (agent_utils.convert_parameter_type) -> Gemini schema types
_GEMINI_TYPE_MAP = {
    "string": "string",
    "str": "string",
    "text": "string",
    "number": "number",
    "float": "number",
    "integer": "integer",
    "int": "integer",
    "boolean": "boolean",
    "bool": "boolean",
    "array": "array",
    "list": "array",
    "object": "object",
    "dict": "object",
}


def _tool_declarations(tools: List[Any]) -> List[Dict[str, Any]]:
    """Map workflow BaseTool objects (agents/base_tool.py) to Live API function declarations.

    Tool parameters use the workflow format {name: {type, description, required, default}}
    (see agent_utils.validate_tool_parameters).
    """
    declarations = []
    for tool in tools:
        declaration: Dict[str, Any] = {
            "name": tool.name,
            "description": tool.description or "",
        }
        parameters = getattr(tool, "parameters", None) or {}
        if parameters:
            properties: Dict[str, Any] = {}
            required: List[str] = []
            for param_name, param_info in parameters.items():
                if not isinstance(param_info, dict):
                    param_info = {}
                prop: Dict[str, Any] = {
                    "type": _GEMINI_TYPE_MAP.get(str(param_info.get("type", "string")).lower(), "string"),
                }
                if param_info.get("description"):
                    prop["description"] = param_info["description"]
                properties[param_name] = prop
                if param_info.get("required"):
                    required.append(param_name)
            schema: Dict[str, Any] = {"type": "object", "properties": properties}
            if required:
                schema["required"] = required
            declaration["parameters"] = schema
        declarations.append(declaration)
    return declarations


async def _execute_tool(tools: List[Any], name: str, args: Dict[str, Any]) -> Any:
    """Execute a connected workflow tool by name; errors become tool output."""
    tool = next((t for t in tools if t.name == name), None)
    if tool is None:
        return {"error": f"Unknown tool: {name}"}
    try:
        from app.modules.workflow.agents.agent_utils import validate_tool_parameters

        validated_args = validate_tool_parameters(tool, args or {})
        # BaseTool.invoke wraps node.execute, which is async (same calling
        # convention as ToolAgent._execute_single_tool).
        result = await tool.invoke(**validated_args)
        if isinstance(result, (dict, list, str, int, float, bool)) or result is None:
            return result
        return str(result)
    except Exception as e:
        logger.error("Voice agent tool '%s' failed: %s", name, e, exc_info=True)
        return {"error": str(e)}


def _history_text(turns: List[Dict[str, Any]]) -> str:
    """Render history turns as plain text for system-instruction replay."""
    lines = []
    for turn in turns:
        speaker = "Assistant" if turn["role"] == "model" else "User"
        lines.append(f"{speaker}: {turn['parts'][0]['text']}")
    return "\n".join(lines)


def _history_to_live_turns(history: Any) -> List[Dict[str, Any]]:
    """Convert conversation memory messages into Live API content turns."""
    turns: List[Dict[str, Any]] = []
    if isinstance(history, str):
        if history.strip():
            turns.append({"role": "user", "parts": [{"text": history}]})
        return turns
    for msg in history or []:
        role = msg.get("role", "user") if isinstance(msg, dict) else "user"
        content = msg.get("content") if isinstance(msg, dict) else msg
        if isinstance(content, dict):
            content = content.get("message") or content.get("response") or str(content)
        if not isinstance(content, str) or not content.strip():
            continue
        turns.append({
            "role": "model" if role in ("assistant", "ai", "model") else "user",
            "parts": [{"text": content}],
        })
    return turns
