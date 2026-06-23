"""
Shared Gemini Live helpers.

Transport/agent-agnostic building blocks for any node or service that talks to
the Gemini Live API: assembling the `LiveConnectConfig`, mapping workflow tools
to Live function declarations, executing a connected tool by name, replaying
conversation memory as content turns, and explaining the Live API's opaque
session-setup rejection. Kept out of the Voice Agent node so other live engines
(e.g. `GeminiLiveAgent`) can reuse them.
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DEFAULT_LIVE_MODEL = "gemini-3.1-flash-live-preview"
DEFAULT_VOICE = "Kore"


def int_or_none(value: Any) -> Optional[int]:
    """Parse an int from node config, treating blank/None as unset."""
    if value in (None, "", "null", "None"):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def explain_live_error(error_message: str) -> str:
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


def build_live_config(cfg: Dict[str, Any], *, system_prompt: str, tools: List[Any]) -> Dict[str, Any]:
    """Build the full Gemini Live `connect` config from the node config.

    The single source of truth for the Live `LiveConnectConfig`, used by both the
    single-turn (record/send) path and the persistent live session. `cfg` is the
    node's resolved config; `system_prompt` is passed in because the single-turn
    path folds replayed history into it.

    Optional knobs (all opt-in; absent unless configured) — verify availability
    against the pinned google-genai version, native-audio models reject some:
      voice/language, temperature, maxOutputTokens, VAD tuning (vadSilenceMs,
      vadStartSensitivity, vadEndSensitivity), proactiveAudio, contextCompression.
    """
    live_config: Dict[str, Any] = {
        "response_modalities": ["AUDIO"],
        "system_instruction": system_prompt,
        "speech_config": {
            "voice_config": {
                "prebuilt_voice_config": {"voice_name": cfg.get("voice") or DEFAULT_VOICE}
            }
        },
        "input_audio_transcription": {},
        "output_audio_transcription": {},
    }
    if cfg.get("language"):
        live_config["speech_config"]["language_code"] = cfg["language"]

    declarations = tool_declarations(tools)
    if declarations:
        live_config["tools"] = [{"function_declarations": declarations}]

    # Generation controls
    if cfg.get("temperature") not in (None, ""):
        try:
            live_config["temperature"] = float(cfg["temperature"])
        except (TypeError, ValueError):
            pass
    max_tokens = int_or_none(cfg.get("maxOutputTokens"))
    if max_tokens:
        live_config["max_output_tokens"] = max_tokens

    # Turn-taking / barge-in (server-side VAD) tuning
    vad: Dict[str, Any] = {}
    silence = int_or_none(cfg.get("vadSilenceMs"))
    if silence is not None:
        vad["silence_duration_ms"] = silence
    if cfg.get("vadStartSensitivity"):
        vad["start_of_speech_sensitivity"] = cfg["vadStartSensitivity"]
    if cfg.get("vadEndSensitivity"):
        vad["end_of_speech_sensitivity"] = cfg["vadEndSensitivity"]
    if vad:
        live_config["realtime_input_config"] = {"automatic_activity_detection": vad}

    # Let the model stay silent on irrelevant input
    if cfg.get("proactiveAudio"):
        live_config["proactivity"] = {"proactive_audio": True}

    # Sliding-window context compression for long calls
    if cfg.get("contextCompression"):
        live_config["context_window_compression"] = {"sliding_window": {}}

    return live_config


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


def tool_declarations(tools: List[Any]) -> List[Dict[str, Any]]:
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


async def execute_workflow_tool(tools: List[Any], name: str, args: Dict[str, Any]) -> Any:
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
        logger.error("Workflow tool '%s' failed: %s", name, e, exc_info=True)
        return {"error": str(e)}


def history_text(turns: List[Dict[str, Any]]) -> str:
    """Render history turns as plain text for system-instruction replay."""
    lines = []
    for turn in turns:
        speaker = "Assistant" if turn["role"] == "model" else "User"
        lines.append(f"{speaker}: {turn['parts'][0]['text']}")
    return "\n".join(lines)


def history_to_live_turns(history: Any) -> List[Dict[str, Any]]:
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
