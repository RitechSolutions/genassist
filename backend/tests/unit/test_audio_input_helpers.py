"""Unit tests for shared audio input extraction helpers and Gemini PCM->WAV wrapping."""

import base64
import io
import wave

import pytest

from app.modules.workflow.audio.audio_input import (
    extract_audio_input,
    extract_text_input,
    pcm_to_wav,
    wav_to_pcm16k,
)

_AUDIO_BYTES = b"x" * 200
_AUDIO_B64 = base64.b64encode(_AUDIO_BYTES).decode("utf-8")


class TestExtractTextInput:
    def test_audio_dict_is_not_text(self):
        assert extract_text_input({"type": "audio", "data": _AUDIO_B64}) is None

    def test_dict_with_audio_data_is_not_text(self):
        assert extract_text_input({"message": "hi", "audio_data": {}}) is None

    def test_message_dict_returns_text(self):
        assert extract_text_input({"message": " hello "}) == "hello"

    def test_plain_string_returns_text(self):
        assert extract_text_input("what is the weather?") == "what is the weather?"

    def test_base64_string_is_not_text(self):
        assert extract_text_input(_AUDIO_B64) is None


class TestExtractAudioInput:
    def test_audio_dict(self):
        audio_bytes, audio_format = extract_audio_input(
            {"type": "audio", "data": _AUDIO_B64, "encoding": "base64", "format": "webm"}
        )
        assert audio_bytes == _AUDIO_BYTES
        assert audio_format == "webm"

    def test_nested_audio_data_key(self):
        audio_bytes, audio_format = extract_audio_input(
            {
                "message": "[Voice message]",
                "audio_data": {"type": "audio", "data": _AUDIO_B64, "encoding": "base64", "format": "wav"},
            }
        )
        assert audio_bytes == _AUDIO_BYTES
        assert audio_format == "wav"

    def test_bare_base64_string_defaults_to_mp3(self):
        audio_bytes, audio_format = extract_audio_input(_AUDIO_B64)
        assert audio_bytes == _AUDIO_BYTES
        assert audio_format == "mp3"

    def test_too_small_audio_rejected(self):
        small = base64.b64encode(b"tiny").decode("utf-8")
        audio_bytes, _ = extract_audio_input({"type": "audio", "data": small})
        assert audio_bytes is None

    def test_none_input(self):
        audio_bytes, _ = extract_audio_input(None)
        assert audio_bytes is None


class TestWavToPcm16k:
    def test_16k_wav_passthrough(self):
        pcm = b"\x00\x01" * 1600
        assert wav_to_pcm16k(pcm_to_wav(pcm, rate=16000), "wav") == pcm

    def test_resamples_other_rates(self):
        pcm_44k = b"\x00\x01" * 44100
        out = wav_to_pcm16k(pcm_to_wav(pcm_44k, rate=44100), "wav")
        # 1 second at 44.1 kHz s16 mono -> ~1 second at 16 kHz s16 mono
        assert abs(len(out) - 32000) < 200

    def test_raw_pcm_passthrough(self):
        assert wav_to_pcm16k(b"\x00\x01" * 10, "pcm") == b"\x00\x01" * 10

    def test_compressed_formats_rejected(self):
        with pytest.raises(ValueError, match="webm"):
            wav_to_pcm16k(b"x" * 200, "webm")


class TestPcmToWav:
    def test_wraps_pcm_with_riff_header(self):
        pcm = b"\x00\x01" * 2400
        wav_bytes = pcm_to_wav(pcm)
        assert wav_bytes[:4] == b"RIFF"
        with wave.open(io.BytesIO(wav_bytes), "rb") as wav_file:
            assert wav_file.getnchannels() == 1
            assert wav_file.getsampwidth() == 2
            assert wav_file.getframerate() == 24000
            assert wav_file.readframes(wav_file.getnframes()) == pcm
