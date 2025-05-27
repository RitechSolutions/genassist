import whisper
from app.core.config.settings import settings
import tempfile
import os
import logging
import asyncio

from app.schemas.conversation_transcript import TranscriptSegment

logger = logging.getLogger(__name__)

# Initialize the default model
current_model_name = settings.DEFAULT_WHISPER_MODEL
model = whisper.load_model(current_model_name)  # Default model

def set_whisper_model(model_name: str):
    """
    Loads a new Whisper model if different from the currently loaded one.
    """
    global model, current_model_name
    if model_name != current_model_name:
        logger.debug(f"Switching Whisper model from {current_model_name} to {model_name}")
        model = whisper.load_model(model_name)
        current_model_name = model_name
    logger.debug(f"Transcribing audio file with {current_model_name}")

async def transcribe_audio_whisper(recording_path:str, whisper_model: str = settings.DEFAULT_WHISPER_MODEL):
    try:
        # Ensure the correct model is loaded
        set_whisper_model(whisper_model)
        # Use Whisper to transcribe the audio
        result = await asyncio.to_thread(model.transcribe, recording_path)
        return result

    except Exception as e:
        return {"error": str(e)}

async def transcribe_audio_whisper_no_save(file, whisper_model: str = settings.DEFAULT_WHISPER_MODEL):
    try:
        # Ensure the correct model is loaded
        set_whisper_model(whisper_model)

        # Save the uploaded file to a temporary location
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as temp_file:
            temp_file.write(file.file.read())
            temp_file_path = temp_file.name

        # Use Whisper to transcribe the audio
        result = await asyncio.to_thread(model.transcribe, temp_file_path)

        # Clean up temporary file
        os.remove(temp_file_path)

        return result

    except Exception as e:
        return {"error": str(e)}

def transcribe_audio_after_diarization(audio_chunks, speaker_segments)-> list[TranscriptSegment]:
    transcript = []

    for segment in speaker_segments:
        speaker = segment["speaker"]
        start_time = segment["start"]
        end_time = segment["end"]

        # Retrieve the corresponding audio chunk
        if speaker in audio_chunks:
            chunk = audio_chunks[speaker].pop(0)  # Take the first available chunk

            # Export chunk temporarily
            chunk.export("temp.wav", format="wav")

            # Run transcription on the audio segment
            result = model.transcribe("temp.wav", language="en")
            text = result["text"]

            # Append to transcript list
            transcript.append(TranscriptSegment(round(start_time, 2), round(end_time, 2), speaker, text))

    #  Sort transcript by `start_time`
    sorted_transcript = sorted(transcript, key=lambda x: x.start_time)

    return sorted_transcript



