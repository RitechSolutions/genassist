import io
import logging
from typing import Any, Dict, List

from app.modules.workflow.audio.base import (
    BaseSTTProvider,
    BaseTTSProvider,
    register_stt_provider,
    register_tts_provider,
)
from app.schemas.dynamic_form_schemas.base import FieldSchema

logger = logging.getLogger(__name__)

_FORM_SCHEMA: List[FieldSchema] = [
    FieldSchema(
        name="service_account_json",
        type="password",
        label="Service Account JSON",
        required=True,
        placeholder='Paste your service account JSON key',
        description="Google Cloud service account credentials in JSON format.",
        encrypted=True,
    ),
]


@register_tts_provider("google_cloud")
class GoogleCloudTTSProvider(BaseTTSProvider):
    DISPLAY_NAME = "Google Cloud"
    FORM_SCHEMA = _FORM_SCHEMA
    VOICES = [
        {"value": "en-US-Neural2-A", "label": "en-US Neural2-A (Female)"},
        {"value": "en-US-Neural2-C", "label": "en-US Neural2-C (Male)"},
        {"value": "en-US-Neural2-D", "label": "en-US Neural2-D (Male)"},
        {"value": "en-US-Neural2-F", "label": "en-US Neural2-F (Female)"},
        {"value": "en-US-Studio-O", "label": "en-US Studio-O (Female)"},
        {"value": "en-US-Studio-Q", "label": "en-US Studio-Q (Male)"},
        {"value": "en-US-Wavenet-A", "label": "en-US Wavenet-A (Female)"},
        {"value": "en-US-Wavenet-B", "label": "en-US Wavenet-B (Male)"},
    ]
    MODELS = [
        {"value": "neural2", "label": "Neural2"},
        {"value": "studio", "label": "Studio"},
        {"value": "wavenet", "label": "WaveNet"},
        {"value": "standard", "label": "Standard"},
    ]
    FORMATS = [
        {"value": "mp3", "label": "MP3"},
        {"value": "wav", "label": "WAV (LINEAR16)"},
        {"value": "ogg", "label": "OGG Opus"},
    ]
    SUPPORTS_SPEED = True

    async def synthesize(self, text: str, config: Dict[str, Any]) -> bytes:
        import json
        from google.cloud import texttospeech_v1 as texttospeech
        from google.oauth2 import service_account

        creds_json = self.connection_data["service_account_json"]
        if isinstance(creds_json, str):
            creds_json = json.loads(creds_json)
        credentials = service_account.Credentials.from_service_account_info(creds_json)

        client = texttospeech.TextToSpeechAsyncClient(credentials=credentials)

        voice_name = config.get("voice", "en-US-Neural2-A")
        language_code = "-".join(voice_name.split("-")[:2])

        voice = texttospeech.VoiceSelectionParams(
            language_code=language_code,
            name=voice_name,
        )

        fmt = config.get("output_format", "mp3")
        encoding_map = {
            "mp3": texttospeech.AudioEncoding.MP3,
            "wav": texttospeech.AudioEncoding.LINEAR16,
            "ogg": texttospeech.AudioEncoding.OGG_OPUS,
        }

        speed = float(config.get("speed", 1.0))
        audio_config = texttospeech.AudioConfig(
            audio_encoding=encoding_map.get(fmt, texttospeech.AudioEncoding.MP3),
            speaking_rate=speed,
        )

        synthesis_input = texttospeech.SynthesisInput(text=text)
        response = await client.synthesize_speech(
            input=synthesis_input, voice=voice, audio_config=audio_config
        )
        return response.audio_content


@register_stt_provider("google_cloud")
class GoogleCloudSTTProvider(BaseSTTProvider):
    DISPLAY_NAME = "Google Cloud"
    FORM_SCHEMA = _FORM_SCHEMA
    MODELS = [
        {"value": "latest_long", "label": "Latest Long"},
        {"value": "latest_short", "label": "Latest Short"},
        {"value": "chirp", "label": "Chirp"},
        {"value": "chirp_2", "label": "Chirp 2"},
    ]
    RESPONSE_FORMATS = [
        {"value": "text", "label": "Plain Text"},
    ]
    SUPPORTS_TEMPERATURE = False

    async def transcribe(self, audio_bytes: bytes, audio_format: str, config: Dict[str, Any]) -> str:
        import json
        from google.cloud import speech_v2 as speech
        from google.oauth2 import service_account

        creds_json = self.connection_data["service_account_json"]
        if isinstance(creds_json, str):
            creds_json = json.loads(creds_json)
        credentials = service_account.Credentials.from_service_account_info(creds_json)
        project_id = creds_json.get("project_id", "")

        client = speech.SpeechAsyncClient(credentials=credentials)

        encoding_map = {
            "wav": speech.ExplicitDecodingConfig.AudioEncoding.LINEAR16,
            "mp3": speech.ExplicitDecodingConfig.AudioEncoding.MP3,
            "flac": speech.ExplicitDecodingConfig.AudioEncoding.FLAC,
            "ogg": speech.ExplicitDecodingConfig.AudioEncoding.OGG_OPUS,
            "webm": speech.ExplicitDecodingConfig.AudioEncoding.WEBM_OPUS,
        }

        model = config.get("model", "latest_long")
        language = config.get("language", "en-US")

        recognizer = f"projects/{project_id}/locations/global/recognizers/_"

        recognition_config = speech.RecognitionConfig(
            auto_decoding_config=speech.AutoDetectDecodingConfig(),
            model=model,
            language_codes=[language],
        )

        request = speech.RecognizeRequest(
            recognizer=recognizer,
            config=recognition_config,
            content=audio_bytes,
        )

        response = await client.recognize(request=request)

        texts = []
        for result in response.results:
            if result.alternatives:
                texts.append(result.alternatives[0].transcript)
        return " ".join(texts)
