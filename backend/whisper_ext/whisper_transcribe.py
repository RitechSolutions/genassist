from pathlib import Path
import re
import aiofiles
from fastapi import FastAPI, Form, UploadFile, File
from typing import Literal, Optional, Tuple, Union
import whisper
import os
import logging
import asyncio
from pydantic import BaseModel, Field
logger = logging.getLogger(__name__)


import tempfile


def sanitize_file_suffix(filename: Optional[str]) -> str:
    """
    Extract and sanitize the file suffix from a filename.
    Only allows alphanumeric characters and dots to prevent path traversal.

    Args:
        filename: The original filename from the upload

    Returns:
        A safe suffix string (e.g., ".mp3") or ".tmp" if invalid
    """
    if not filename:
        return ".tmp"

    suffix = Path(filename).suffix
    # Only allow alphanumeric characters and dots in suffix
    if suffix and re.match(r'^\.[\w]+$', suffix):
        return suffix
    return ".tmp"


def safe_remove_temp_file(file_path: str) -> None:
    """
    Safely remove a temporary file after validating it's in the system temp directory.
    This prevents path traversal attacks by ensuring we only delete files in temp locations.

    Args:
        file_path: The path to the temp file to remove

    Raises:
        ValueError: If the file is not in a temp directory
    """
    if not file_path:
        return

    resolved_path = Path(file_path).resolve()
    temp_dir = Path(tempfile.gettempdir()).resolve()

    # Verify the file is within the temp directory
    try:
        resolved_path.relative_to(temp_dir)
    except ValueError:
        raise ValueError(f"Security error: Attempted to delete file outside temp directory: {file_path}")

    if resolved_path.exists():
        resolved_path.unlink()
DEFAULT_WHISPER_MODEL = os.getenv('DEFAULT_WHISPER_MODEL', 'base.en') #load default whisper model from environment or

# Initialize the default model
current_model_name = DEFAULT_WHISPER_MODEL
model = whisper.load_model(current_model_name)  # Default model

app = FastAPI()


class WhisperOptions(BaseModel):
    """Options for Whisper transcription with defaults and descriptions."""

    # Basic options
    language: Optional[str] = Field(
            None,
            description="Language code (e.g., 'en', 'es', 'fr') or None for auto-detection"
            )
    task: Literal["transcribe", "translate"] = Field(
            "transcribe",
            description="Task type: transcribe audio or translate to English"
            )
    temperature: Union[float, Tuple[float, ...]] = Field(
            0.0,
            description="Sampling temperature (0.0-1.0). Higher values increase randomness"
            )

    # Advanced options
    initial_prompt: Optional[str] = Field(
            None,
            description="Initial prompt to guide transcription style and context"
            )
    word_timestamps: bool = Field(
            False,
            description="Generate word-level timestamps in addition to segment-level"
            )
    condition_on_previous_text: bool = Field(
            True,
            description="Use previous text segments for context (improves consistency)"
            )
    compression_ratio_threshold: float = Field(
            2.4,
            description="Threshold for detecting repetitive text (default: 2.4)"
            )
    logprob_threshold: float = Field(
            -1.0,
            description="Log probability threshold for segment filtering (default: -1.0)"
            )
    no_speech_threshold: float = Field(
            0.6,
            description="Silence detection threshold (0.0-1.0, default: 0.6)"
            )
    verbose: bool = Field(
            False,
            description="Enable verbose output during transcription"
            )
    best_of: Optional[int] = Field(
            None,
            description="Number of candidates when sampling (default: 5)"
            )
    beam_size: Optional[int] = Field(
            None,
            description="Number of beams in beam search (default: 5)"
            )
    patience: Optional[float] = Field(
            None,
            description="Patience value for beam decoding"
            )

@app.post("/transcribe")
async def transcribe(file: UploadFile = File(...),
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
        logger.debug(f"Switching Whisper model from {current_model_name} to {model_name}")
        model = whisper.load_model(model_name)
        current_model_name = model_name
    logger.debug(f"Transcribing audio file with {current_model_name}")


async def transcribe_audio_whisper_no_save(file: UploadFile, whisper_options: str, model_name: str):
    temp_file_path = None
    try:
        if whisper_options:
            options = WhisperOptions.model_validate_json(whisper_options)
            options_dict = options.model_dump(exclude_none=True)

        set_whisper_model(model_name)

        # Read file asynchronously
        file_bytes = await file.read()
        # Sanitize the suffix to prevent path traversal
        suffix = sanitize_file_suffix(file.filename)

        # Use async temporary file
        async with aiofiles.tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            await temp_file.write(file_bytes)
            temp_file_path = temp_file.name

        if whisper_options:
            result = await asyncio.to_thread(model.transcribe, temp_file_path, **options_dict)
        else:
            result = await asyncio.to_thread(model.transcribe, temp_file_path)

        return result

    except Exception as e:
        return {"error": str(e)}
    finally:
        # Clean up temp file with path validation to prevent path traversal
        if temp_file_path:
            try:
                safe_remove_temp_file(temp_file_path)
            except Exception as cleanup_error:
                logger.warning(f"Failed to remove temporary file {temp_file_path}: {cleanup_error}")


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
        status["gpu_devices"] = [torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())]
        status["gpu_memory_allocated_mb"] = round(torch.cuda.memory_allocated(0) / 1024 ** 2, 1)
        status["gpu_memory_reserved_mb"] = round(torch.cuda.memory_reserved(0) / 1024 ** 2, 1)

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



######################
## Chunked transcription for long audio files
######################

from pydub import AudioSegment
import torch

from faster_whisper import WhisperModel # Use faster-whisper for improved performance on CPU and GPU remove the rgullar whisper if it work
from concurrent.futures import ThreadPoolExecutor

import time
import os


CHUNK_LENGTH_MS = 10 * 60000  # 10 minutes (600 seconds)

GPU_WORKERS = int(os.environ.get("GPU_WORKERS", 1))  # Only one worker can use the GPU at a time (update it as per your system configuration)
CPU_WORKERS = int(os.environ.get("CPU_WORKERS", 4))   # Number of paralel workers for CPU processing (update it as per number of cores  your system has)

#check if Cuda is available and set device accordingly
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# Use a lock to ensure only one GPU transcription runs at a time the rest are forwarded to CPU workers
gpu_lock = asyncio.Lock()
selected_model = "base.en" # set it as default model

cpu_executor = ThreadPoolExecutor(max_workers=CPU_WORKERS)



# Initialize model once
if DEVICE == "cuda":
    model = WhisperModel(
        selected_model,
        device="cuda",
        compute_type="float16"
    )
else:
    model = WhisperModel(
        selected_model,
        device="cpu",
        compute_type="int8"
    )


async def transcribe_chunk(chunk_path: str, options_dict: dict):
    loop = asyncio.get_event_loop()

    if DEVICE == "cuda":
        async with gpu_lock:
            segments, info = await asyncio.to_thread(
                model.transcribe,
                chunk_path,
                **options_dict
            )
            return segments, info, "cuda"
    else:
        segments, info = await loop.run_in_executor(
            cpu_executor,
            lambda: model.transcribe(chunk_path, **options_dict)
        )
        return segments, info, "cpu"

async def transcribe_audio_whisper_chunked(
    file: UploadFile,
    whisper_options: Optional[str], 
    model_name: str
):
    temp_file_path = None
    file_ext = None
    chunk_paths = []

    processing_time=0
    start_time = time.perf_counter()
    end_time = None
    cuda_cpu_used = None

    try:
        options_dict = {}

        # If whisper_options is empty or "{}" → use base.en
        if not whisper_options or whisper_options.strip() == "{}":
            selected_model = model_name if model_name else DEFAULT_WHISPER_MODEL
        else:
            options = WhisperOptions.model_validate_json(whisper_options)
            options_dict = options.model_dump(exclude_none=True)
            selected_model = model_name if model_name else DEFAULT_WHISPER_MODEL

        # Save uploaded file (streaming safer for large files)
        suffix = sanitize_file_suffix(file.filename)

        async with aiofiles.tempfile.NamedTemporaryFile(
            delete=False, suffix=suffix
        ) as temp_file:
            while chunk := await file.read(1024 * 1024):
                await temp_file.write(chunk)
            temp_file_path = temp_file.name
            file_ext = temp_file_path.split(".")[-1].lower()

        # Load & normalize audio
        audio = await asyncio.to_thread(AudioSegment.from_file, temp_file_path)
        audio = audio.set_channels(1).set_frame_rate(16000)

        chunks = [
            audio[i:i + CHUNK_LENGTH_MS]
            for i in range(0, len(audio), CHUNK_LENGTH_MS)
        ]

        full_text = ""
        all_segments = []
        info = {"duration": 0}

        for idx, chunk in enumerate(chunks):
            chunk_path = f"{temp_file_path}_chunk_{idx}.{file_ext}"
            chunk_paths.append(chunk_path)

            await asyncio.to_thread(chunk.export, chunk_path, format=file_ext)

            segments, info, cuda_cpu_used = await transcribe_chunk(chunk_path, options_dict)

            offset_seconds = (idx * CHUNK_LENGTH_MS) / 1000

            for segment in segments:
                adjusted_segment = {
                    "start": segment.start + offset_seconds,
                    "end": segment.end + offset_seconds,
                    "text": segment.text
                }
                all_segments.append(adjusted_segment)
                full_text += segment.text + " "
        end_time = time.perf_counter()

        processing_time = end_time - start_time
        return {
            "text": full_text.strip(),
            "segments": all_segments,
            # "info": info,
            "audio_duration": info.duration if info else None,
            "processing_time": processing_time,
            "model_name": selected_model,
            "device": cuda_cpu_used,
        }

    except Exception as e:
        return {"error": str(e)}

    finally:
        if temp_file_path:
            safe_remove_temp_file(temp_file_path)

        for path in chunk_paths:
            safe_remove_temp_file(path)


# Endpoint for chunked transcription of long audio files with the same options as the regular endpoint
@app.post("/transcribe-long")
async def transcribe(
    file: UploadFile = File(...),
    whisper_options: Optional[str] = Form(None),
    model_name: Optional[str] = DEFAULT_WHISPER_MODEL,
):
    return await transcribe_audio_whisper_chunked(
        file,
        whisper_options, 
        model_name  
    )

