from typing import List

from ..base import ConditionalField, FieldSchema

VOICE_AGENT_NODE_DIALOG_SCHEMA: List[FieldSchema] = [
    FieldSchema(
        name="name",
        type="text",
        label="Node Name",
        required=False,
    ),
    FieldSchema(
        name="voiceProviderId",
        type="select",
        label="Voice Provider",
        required=True,
        placeholder="Select a Gemini audio provider",
        description="Gemini audio provider whose API key is used for the Live API session.",
    ),
    FieldSchema(
        name="model",
        type="select",
        label="Live Model",
        required=False,
        default="gemini-3.1-flash-live-preview",
        options=[
            {"value": "gemini-3.1-flash-live-preview", "label": "Gemini 3.1 Flash Live (Preview)"},
            {"value": "gemini-2.5-flash-native-audio-preview-12-2025", "label": "Gemini 2.5 Flash Native Audio (Preview)"},
        ],
        description="Gemini Live API model used for native speech-to-speech.",
    ),
    FieldSchema(
        name="voice",
        type="select",
        label="Voice",
        required=False,
        default="Kore",
        options=[
            {"value": "Kore", "label": "Kore (Firm)"},
            {"value": "Puck", "label": "Puck (Upbeat)"},
            {"value": "Zephyr", "label": "Zephyr (Bright)"},
            {"value": "Charon", "label": "Charon (Informative)"},
            {"value": "Fenrir", "label": "Fenrir (Excitable)"},
            {"value": "Leda", "label": "Leda (Youthful)"},
            {"value": "Aoede", "label": "Aoede (Breezy)"},
            {"value": "Orus", "label": "Orus (Firm)"},
        ],
        description="Voice used for the spoken reply.",
    ),
    FieldSchema(
        name="language",
        type="text",
        label="Language Code",
        required=False,
        placeholder="e.g. en-US, de-DE (auto-detect if empty)",
        description="Optional BCP-47 language code for the voice output.",
    ),
    FieldSchema(
        name="systemPrompt",
        type="text",
        label="System Prompt",
        required=True,
        default="You are a helpful voice assistant. Keep your spoken answers concise.",
    ),
    FieldSchema(
        name="userPrompt",
        type="text",
        label="Text Fallback Prompt",
        required=False,
        default="{{session.message}}",
        description="Used when the user types a text message instead of sending voice.",
    ),
    FieldSchema(
        name="maxToolCalls",
        type="number",
        label="Max Tool Calls",
        required=False,
        default=10,
        min=1,
        step=1,
        description="Safety cap on tool invocations within a single voice turn.",
    ),
    FieldSchema(
        name="memory",
        type="boolean",
        label="Enable Memory",
        required=True,
    ),
    FieldSchema(
        name="piiMasking",
        type="boolean",
        label="Enable PII Masking",
        required=False,
        default=False,
        description=(
            "Mask PII in the replayed conversation history and text messages. "
            "Note: audio sent to the model cannot be masked."
        ),
    ),
    FieldSchema(
        name="memoryTrimmingMode",
        type="select",
        label="Memory Trimming Mode",
        required=False,
        default="message_count",
        options=[
            {"value": "message_count", "label": "Last N Messages"},
            {"value": "rag_retrieval", "label": "RAG Retrieval"},
        ],
        description="How to limit conversation history replayed into the voice session",
    ),
    FieldSchema(
        name="maxMessages",
        type="number",
        label="Max Messages",
        required=False,
        default=10,
        min=1,
        step=1,
        description="Maximum messages when using message count mode",
        conditional=ConditionalField(
            field="memoryTrimmingMode",
            value="message_count",
        ),
    ),
]
