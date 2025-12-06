from pathlib import Path
import aiofiles
from fastapi import FastAPI, Form, UploadFile, File
from typing import Literal, Optional, Tuple, Union
import whisper
import os
import logging
import asyncio
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
DEFAULT_WHISPER_MODEL = os.getenv(
    "DEFAULT_WHISPER_MODEL", "base.en"
)  # load default whisper model from environment or

# Initialize the default model
current_model_name = DEFAULT_WHISPER_MODEL
model = whisper.load_model(current_model_name)  # Default model

app = FastAPI()


class WhisperOptions(BaseModel):
    """Options for Whisper transcription with defaults and descriptions."""

    # Basic options
    language: Optional[str] = Field(
        None,
        description="Language code (e.g., 'en', 'es', 'fr') or None for auto-detection",
    )
    task: Literal["transcribe", "translate"] = Field(
        "transcribe", description="Task type: transcribe audio or translate to English"
    )
    temperature: Union[float, Tuple[float, ...]] = Field(
        0.0,
        description="Sampling temperature (0.0-1.0). Higher values increase randomness",
    )

    # Advanced options
    initial_prompt: Optional[str] = Field(
        None, description="Initial prompt to guide transcription style and context"
    )
    word_timestamps: bool = Field(
        False, description="Generate word-level timestamps in addition to segment-level"
    )
    condition_on_previous_text: bool = Field(
        True,
        description="Use previous text segments for context (improves consistency)",
    )
    compression_ratio_threshold: float = Field(
        2.4, description="Threshold for detecting repetitive text (default: 2.4)"
    )
    logprob_threshold: float = Field(
        -1.0,
        description="Log probability threshold for segment filtering (default: -1.0)",
    )
    no_speech_threshold: float = Field(
        0.6, description="Silence detection threshold (0.0-1.0, default: 0.6)"
    )
    verbose: bool = Field(
        False, description="Enable verbose output during transcription"
    )
    best_of: Optional[int] = Field(
        None, description="Number of candidates when sampling (default: 5)"
    )
    beam_size: Optional[int] = Field(
        None, description="Number of beams in beam search (default: 5)"
    )
    patience: Optional[float] = Field(
        None, description="Patience value for beam decoding"
    )


@app.post("/transcribe")
async def transcribe(
    file: UploadFile = File(...),
    whisper_options: Optional[str] = Form(None),
    model_name: Optional[str] = DEFAULT_WHISPER_MODEL,
):

    return await transcribe_audio_whisper_no_save(file, whisper_options, model_name)


def set_whisper_model(model_name: str):
    """
    Loads a new Whisper model if different from the currently loaded one.
    """
    global model, current_model_name
    if model_name != current_model_name:
        logger.debug(
            f"Switching Whisper model from {current_model_name} to {model_name}"
        )
        model = whisper.load_model(model_name)
        current_model_name = model_name
    logger.debug(f"Transcribing audio file with {current_model_name}")


async def transcribe_audio_whisper_no_save(
    file: UploadFile, whisper_options: str, model_name: str
):
    temp_file_path = None
    try:
        if whisper_options:
            options = WhisperOptions.model_validate_json(whisper_options)
            options_dict = options.model_dump(exclude_none=True)

        set_whisper_model(model_name)

        # Read file asynchronously
        file_bytes = await file.read()
        suffix = Path(file.filename).suffix if file.filename else ".tmp"

        # Use async temporary file
        async with aiofiles.tempfile.NamedTemporaryFile(
            delete=False, suffix=suffix
        ) as temp_file:
            await temp_file.write(file_bytes)
            temp_file_path = temp_file.name

        if whisper_options:
            result = await asyncio.to_thread(
                model.transcribe, temp_file_path, **options_dict
            )
        else:
            result = await asyncio.to_thread(model.transcribe, temp_file_path)

        return result

    except Exception as e:
        return {"error": str(e)}
    finally:
        # Clean up temp file asynchronously
        if temp_file_path:
            try:
                await aiofiles.os.remove(temp_file_path)
            except Exception as cleanup_error:
                logger.warning(
                    f"Failed to remove temporary file {temp_file_path}: {cleanup_error}"
                )


@app.get("/cuda-status")
async def cuda_status():
    """Check if CUDA is available and being used by Whisper"""
    import torch

    status = {
        "cuda_available": torch.cuda.is_available(),
        "cuda_device_count": torch.cuda.device_count(),
        "pytorch_version": torch.__version__,
        "whisper_model_name": current_model_name,
    }

    if torch.cuda.is_available():
        status["cuda_version"] = torch.version.cuda
        status["gpu_devices"] = [
            torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())
        ]
        status["gpu_memory_allocated_mb"] = round(
            torch.cuda.memory_allocated(0) / 1024**2, 1
        )
        status["gpu_memory_reserved_mb"] = round(
            torch.cuda.memory_reserved(0) / 1024**2, 1
        )

        # Check if current Whisper model is on GPU
        if model is not None:
            model_device = str(next(model.parameters()).device)
            status["whisper_model_device"] = model_device
            status["using_gpu"] = "cuda" in model_device
        else:
            status["whisper_model_device"] = "model not loaded"
            status["using_gpu"] = False
    else:
        status["using_gpu"] = False
        status["whisper_model_device"] = "cpu (cuda not available)"

    return status
