import audioop
import io
import logging
import wave

import httpx

from config import settings

logger = logging.getLogger(__name__)

TTS_VOICE = "alloy"


async def get_openai_session_key(
    lang_code: str = "", input_audio_format: str = "pcm16"
) -> str:
    """Get a temporary session key from OpenAI for realtime transcription."""
    url = "https://api.openai.com/v1/realtime/transcription_sessions"
    headers = {
        "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }

    model = "gpt-4o-transcribe" if not lang_code else "whisper-1"
    if not lang_code:
        lang_code = "en"

    payload = {
        "input_audio_format": input_audio_format,
        "input_audio_transcription": {
            "model": model,
            "prompt": "",
            "language": lang_code,
        },
        "turn_detection": {
            "type": "server_vad",
            "threshold": 0.5,
            "prefix_padding_ms": 300,
            "silence_duration_ms": 500,
        },
        "input_audio_noise_reduction": {"type": "near_field"},
        "include": ["item.input_audio_transcription.logprobs"],
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
        return data["client_secret"]["value"]


async def text_to_speech_openai(text: str) -> bytes | None:
    """Convert text to ulaw audio bytes via OpenAI TTS."""
    api_url = "https://api.openai.com/v1/audio/speech"
    headers = {
        "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    data = {
        "model": "tts-1",
        "input": text,
        "voice": TTS_VOICE,
        "response_format": "wav",
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(api_url, headers=headers, json=data)
            response.raise_for_status()

            wav_data = response.content
            wav_io = io.BytesIO(wav_data)

            with wave.open(wav_io, "rb") as wav_file:
                sample_rate = wav_file.getframerate()
                sample_width = wav_file.getsampwidth()
                channels = wav_file.getnchannels()
                audio_data = wav_file.readframes(wav_file.getnframes())

                if sample_rate != 8000:
                    audio_data, _ = audioop.ratecv(
                        audio_data, sample_width, channels, sample_rate, 8000, None
                    )
                if channels == 2:
                    audio_data = audioop.tomono(audio_data, sample_width, 1, 1)

                return audioop.lin2ulaw(audio_data, sample_width)

        except Exception as exc:
            logger.error(f"TTS error: {exc}")
            return None


async def process_with_agent(agent_id: str, thread_id: str, text: str) -> dict:
    """Call backend internal endpoint to process text with agent."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{settings.BACKEND_URL}/api/internal/agents/execute",
                json={
                    "agent_id": agent_id,
                    "thread_id": thread_id,
                    "text": text,
                },
                headers={"x-internal-secret": settings.WS_INTERNAL_SECRET},
            )
            if resp.status_code != 200:
                return {"success": False, "message": "Backend agent execution failed"}
            return resp.json()
    except Exception as exc:
        logger.error(f"Agent call error: {exc}")
        return {"success": False, "message": str(exc)}

