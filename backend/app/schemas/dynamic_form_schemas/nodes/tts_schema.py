from typing import List
from ..base import FieldSchema

TTS_NODE_DIALOG_SCHEMA: List[FieldSchema] = [
    FieldSchema(
        name="name",
        type="text",
        label="Node Name",
        required=False,
    ),
    FieldSchema(
        name="text",
        type="text",
        label="Text Input",
        required=True,
        placeholder="Enter text or use {{source.message}} to reference the previous node's output",
        description="The text to convert to speech. Supports variable syntax.",
    ),
    FieldSchema(
        name="audioProviderId",
        type="select",
        label="Audio Provider",
        required=True,
        placeholder="Select an audio provider",
        description="Select a configured audio provider for text-to-speech.",
    ),
    FieldSchema(
        name="voice",
        type="select",
        label="Voice",
        required=True,
        default="nova",
        options=[
            {"value": "alloy", "label": "Alloy"},
            {"value": "echo", "label": "Echo"},
            {"value": "fable", "label": "Fable"},
            {"value": "onyx", "label": "Onyx"},
            {"value": "nova", "label": "Nova"},
            {"value": "shimmer", "label": "Shimmer"},
        ],
    ),
    FieldSchema(
        name="model",
        type="select",
        label="Model",
        required=True,
        default="tts-1",
        options=[
            {"value": "tts-1", "label": "TTS-1 (Fast)"},
            {"value": "tts-1-hd", "label": "TTS-1 HD (Quality)"},
        ],
    ),
    FieldSchema(
        name="output_format",
        type="select",
        label="Output Format",
        required=False,
        default="mp3",
        options=[
            {"value": "mp3", "label": "MP3"},
            {"value": "opus", "label": "Opus"},
            {"value": "aac", "label": "AAC"},
            {"value": "flac", "label": "FLAC"},
            {"value": "wav", "label": "WAV"},
            {"value": "pcm", "label": "PCM"},
        ],
    ),
    FieldSchema(
        name="speed",
        type="number",
        label="Speed",
        required=False,
        default=1.0,
        min=0.25,
        max=4.0,
        step=0.25,
        description="Speech speed (0.25 to 4.0)",
    ),
]
