from typing import List
from ..base import FieldSchema

STT_NODE_DIALOG_SCHEMA: List[FieldSchema] = [
    FieldSchema(
        name="name",
        type="text",
        label="Node Name",
        required=False,
    ),
    FieldSchema(
        name="audio_source",
        type="text",
        label="Audio Source",
        required=True,
        placeholder="Use {{source.output}} to reference the previous node's audio output",
        description="Reference to the audio data from a connected TTS or audio-producing node.",
    ),
    FieldSchema(
        name="audioProviderId",
        type="select",
        label="Audio Provider",
        required=True,
        placeholder="Select an audio provider",
        description="Select a configured audio provider for speech-to-text.",
    ),
    FieldSchema(
        name="model",
        type="select",
        label="Model",
        required=True,
        default="whisper-1",
        options=[
            {"value": "whisper-1", "label": "Whisper-1"},
            {"value": "gpt-4o-transcribe", "label": "GPT-4o Transcribe"},
            {"value": "gpt-4o-mini-transcribe", "label": "GPT-4o Mini Transcribe"},
        ],
    ),
    FieldSchema(
        name="language",
        type="text",
        label="Language Code",
        required=False,
        placeholder="e.g., en, es, fr (leave empty for auto-detect)",
        description="ISO 639-1 language code. Leave empty for automatic detection.",
    ),
    FieldSchema(
        name="response_format",
        type="select",
        label="Response Format",
        required=False,
        default="text",
        options=[
            {"value": "text", "label": "Plain Text"},
            {"value": "json", "label": "JSON"},
            {"value": "verbose_json", "label": "Verbose JSON"},
        ],
    ),
    FieldSchema(
        name="temperature",
        type="number",
        label="Temperature",
        required=False,
        default=0.0,
        min=0.0,
        max=1.0,
        step=0.1,
        description="Sampling temperature (0.0 for deterministic)",
    ),
]
