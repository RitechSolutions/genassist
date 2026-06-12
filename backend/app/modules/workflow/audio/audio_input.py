"""Shared audio helpers for workflow nodes.

Node outputs carry audio as a payload dict ``{"type": "audio", "data":
"<b64>", "encoding": "base64", "format": "mp3"}`` (see ``build_audio_payload``,
used by TTSNode / VoiceAgentNode). This module both produces those payloads and
normalizes the possible input shapes (dict, nested ``audio_data``, JSON string,
bare base64 string) back into raw bytes, plus the WAV<->PCM conversions used by
the Gemini providers and the Live API voice agent.
"""

import audioop  # noqa: deprecated in 3.12, removed in 3.13; only stdlib resampling without ffmpeg
import base64
import io
import json
import logging
import wave
from typing import Any, Dict

logger = logging.getLogger(__name__)

# Gemini Live API expects 16-bit mono PCM @ 16 kHz input.
LIVE_API_SAMPLE_RATE = 16000
LIVE_API_INPUT_MIME = f"audio/pcm;rate={LIVE_API_SAMPLE_RATE}"
# Gemini TTS / Live API output is raw PCM: signed 16-bit little-endian, 24 kHz, mono.
GEMINI_PCM_SAMPLE_RATE = 24000
_PCM_SAMPLE_WIDTH = 2


def build_audio_payload(audio_bytes: bytes, audio_format: str) -> Dict[str, Any]:
    """Build the canonical base64 audio payload exchanged between nodes."""
    return {
        "type": "audio",
        "format": audio_format,
        "encoding": "base64",
        "data": base64.b64encode(audio_bytes).decode("utf-8"),
    }


def pcm_to_wav(
    pcm: bytes,
    rate: int = GEMINI_PCM_SAMPLE_RATE,
    channels: int = 1,
    sample_width: int = _PCM_SAMPLE_WIDTH,
) -> bytes:
    """Wrap raw PCM frames in a WAV container."""
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(sample_width)
        wav_file.setframerate(rate)
        wav_file.writeframes(pcm)
    return buffer.getvalue()


def wav_to_pcm16k(audio_bytes: bytes, audio_format: str) -> bytes:
    """Convert WAV (or raw PCM) input to 16-bit mono PCM @ 16 kHz as required
    by the Gemini Live API. Compressed formats (webm/mp3/...) are rejected —
    the backend has no decoder for them."""
    if audio_format in ("pcm", "pcm16"):
        return audio_bytes
    if audio_format not in ("wav", "wave"):
        raise ValueError(
            f"Unsupported audio format '{audio_format}' for the Voice Agent: "
            "native audio requires WAV (16-bit PCM) input."
        )
    with wave.open(io.BytesIO(audio_bytes), "rb") as wav_file:
        rate = wav_file.getframerate()
        channels = wav_file.getnchannels()
        sample_width = wav_file.getsampwidth()
        frames = wav_file.readframes(wav_file.getnframes())
    if sample_width != 2:
        frames = audioop.lin2lin(frames, sample_width, 2)
    if channels == 2:
        frames = audioop.tomono(frames, 2, 0.5, 0.5)
    elif channels != 1:
        raise ValueError(f"Unsupported channel count: {channels}")
    if rate != LIVE_API_SAMPLE_RATE:
        frames, _ = audioop.ratecv(frames, 2, 1, rate, LIVE_API_SAMPLE_RATE, None)
    return frames


def extract_text_input(source_output: Any) -> str | None:
    """If the input is plain text (not audio), return it directly."""
    if isinstance(source_output, dict):
        if source_output.get("type") == "audio":
            return None
        if "audio_data" in source_output:
            return None
        msg = source_output.get("message") or source_output.get("response")
        if isinstance(msg, str) and msg.strip():
            return msg.strip()
        return None
    if isinstance(source_output, str) and source_output.strip():
        try:
            parsed = json.loads(source_output)
            if isinstance(parsed, dict):
                return extract_text_input(parsed)
        except (json.JSONDecodeError, ValueError):
            pass
        try:
            base64.b64decode(source_output, validate=True)
            return None
        except Exception:
            return source_output.strip()
    return None


def extract_audio_input(source_output: Any) -> tuple[bytes | None, str]:
    """Extract raw audio bytes and format from a node input. Returns (bytes | None, format)."""
    if isinstance(source_output, dict):
        if source_output.get("type") == "audio" and source_output.get("data"):
            encoding = source_output.get("encoding", "base64")
            audio_format = source_output.get("format", "mp3")
            if encoding == "base64":
                audio_bytes = base64.b64decode(source_output["data"])
                if len(audio_bytes) > 100:
                    return audio_bytes, audio_format
                logger.warning("Decoded audio data too small (%d bytes), likely invalid", len(audio_bytes))
                return None, audio_format
        if "audio_data" in source_output:
            return extract_audio_input(source_output["audio_data"])

    if isinstance(source_output, str) and source_output:
        try:
            parsed = json.loads(source_output)
            if isinstance(parsed, dict):
                return extract_audio_input(parsed)
        except (json.JSONDecodeError, ValueError):
            pass
        try:
            audio_bytes = base64.b64decode(source_output)
            if len(audio_bytes) > 100:
                return audio_bytes, "mp3"
            logger.warning("Decoded audio data too small (%d bytes), likely invalid", len(audio_bytes))
        except Exception:
            logger.warning("audio_source string is not valid base64")

    return None, "mp3"
