import asyncio
import logging
import aiofiles
import httpx
import mimetypes
import tempfile
from typing import Any, Dict, List, Optional, Union
from pathlib import Path
from starlette.datastructures import UploadFile
from pydub import AudioSegment
from app.core.config.settings import settings
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException


logger = logging.getLogger(__name__)


def _guess_mime(path: str) -> str:
    mt, _ = mimetypes.guess_type(path)
    return mt or "application/octet-stream"


async def _post_with_file(
        url: str,
        file_source: Union[str, UploadFile],
        form_fields: Dict[str, Any],
        client: httpx.AsyncClient,
        ) -> httpx.Response:
    try:
        if isinstance(file_source, UploadFile):
            await file_source.seek(0)
            filename = file_source.filename or "upload"
            mime = file_source.content_type or _guess_mime(filename)

            logger.debug(f"Streaming UploadFile {filename} with MIME type {mime}")

            files = {"file": (filename, file_source.file, mime)}
            return await client.post(url, data=form_fields, files=files)

        else:
            file_path = file_source
            file_path_obj = Path(file_path)

            if not file_path_obj.exists():
                raise FileNotFoundError(f"Audio file not found: {file_path}")

            filename = file_path_obj.name
            mime = _guess_mime(file_path)
            logger.debug(f"Uploading file {filename} with MIME type {mime}")

            try:
                async with aiofiles.open(file_path, "rb") as f:
                    file_bytes = await f.read()
            except Exception as e:
                logger.error(f"Failed to read file {file_path}: {e}")
                raise

            files = {"file": (filename, file_bytes, mime)}
            return await client.post(url, data=form_fields, files=files)

    except Exception as e:
        logger.error(f"Failed to post file: {e}")
        raise


async def _transcribe_single_chunk(
        chunk_path: str,
        form_fields: Dict[str, Any],
        client: httpx.AsyncClient,
        ) -> Dict[str, Any]:
    """Send a single audio chunk to the Whisper service and return the result."""
    resp = await _post_with_file(
        settings.WHISPER_TRANSCRIBE_SERVICE,
        chunk_path,
        form_fields,
        client,
    )
    resp.raise_for_status()

    result = resp.json()
    if not isinstance(result, dict):
        raise AppException(ErrorKey.ERROR_RESPONSE_FORMAT)
    if result.get("error"):
        logger.error(f"Error in whisper result for chunk {chunk_path}: {result['error']}")
        raise AppException(ErrorKey.ERROR_RETURN_WHISPER_SERVICE)

    return result


def _split_audio_to_chunks(audio_path: str, chunk_duration_ms: int) -> List[str]:
    """Split an audio file into chunks and return list of temp file paths."""
    audio = AudioSegment.from_file(audio_path)
    audio = audio.set_channels(1).set_frame_rate(16000)

    if len(audio) <= chunk_duration_ms:
        return []  # No splitting needed

    file_ext = Path(audio_path).suffix.lstrip(".") or "wav"
    chunk_paths = []

    for i in range(0, len(audio), chunk_duration_ms):
        chunk = audio[i:i + chunk_duration_ms]
        chunk_file = tempfile.NamedTemporaryFile(
            delete=False, suffix=f".{file_ext}", prefix="whisper_chunk_"
        )
        chunk_path = chunk_file.name
        chunk_file.close()
        chunk.export(chunk_path, format=file_ext)
        chunk_paths.append(chunk_path)

    return chunk_paths


def _merge_chunk_results(
        chunk_results: List[Dict[str, Any]],
        chunk_duration_ms: int,
        ) -> Dict[str, Any]:
    """Merge results from multiple chunk transcriptions with adjusted timestamps."""
    full_text_parts = []
    all_segments = []

    for idx, result in enumerate(chunk_results):
        offset_seconds = (idx * chunk_duration_ms) / 1000.0
        text = result.get("text", "")
        if text:
            full_text_parts.append(text.strip())

        for segment in result.get("segments", []):
            adjusted_segment = {
                "start": segment["start"] + offset_seconds,
                "end": segment["end"] + offset_seconds,
                "text": segment["text"],
            }
            all_segments.append(adjusted_segment)

    merged = {
        "text": " ".join(full_text_parts),
        "segments": all_segments,
    }

    # Preserve extra fields from the last chunk result
    last = chunk_results[-1] if chunk_results else {}
    for key in ("model_name", "device"):
        if key in last:
            merged[key] = last[key]

    # Sum up processing times and audio durations
    total_processing = sum(r.get("processing_time", 0) for r in chunk_results if r.get("processing_time"))
    total_duration = sum(r.get("audio_duration", 0) for r in chunk_results if r.get("audio_duration"))
    if total_processing:
        merged["processing_time"] = total_processing
    if total_duration:
        merged["audio_duration"] = total_duration

    return merged


def _cleanup_temp_files(paths: List[str]) -> None:
    """Remove temporary chunk files."""
    for path in paths:
        try:
            p = Path(path)
            if p.exists():
                p.unlink()
        except Exception as e:
            logger.warning(f"Failed to remove temp file {path}: {e}")


async def _save_source_to_temp(recording_source: Union[str, UploadFile]) -> str:
    """Save the recording source to a temp file and return its path. Caller must clean up."""
    if isinstance(recording_source, UploadFile):
        await recording_source.seek(0)
        suffix = Path(recording_source.filename or "upload.wav").suffix or ".wav"
        async with aiofiles.tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            while chunk := await recording_source.read(1024 * 1024):
                await tmp.write(chunk)
            return tmp.name
    else:
        return recording_source  # Already a file path on disk


async def transcribe_audio_whisper(
        recording_source: Union[str, UploadFile],
        whisper_model: Optional[str] = settings.DEFAULT_WHISPER_MODEL,
        whisper_options: Optional[str] = None,
        ) -> Dict[str, Any]:
    """Transcribe audio using Whisper service.

    For audio longer than WHISPER_CHUNK_DURATION_MS (default 5 minutes),
    splits into chunks and transcribes them in parallel for faster responses.
    """
    if whisper_model is None:
        whisper_model = settings.DEFAULT_WHISPER_MODEL

    source_info = recording_source.filename if isinstance(recording_source, UploadFile) else recording_source
    logger.info(f"Starting transcription for {source_info} using model {whisper_model}")

    temp_audio_path = None
    chunk_paths = []
    is_temp_source = isinstance(recording_source, UploadFile)

    try:
        # Save to temp file if needed (for UploadFile or to probe duration)
        temp_audio_path = await _save_source_to_temp(recording_source)

        # Try splitting into chunks (requires ffprobe)
        try:
            chunk_paths = await asyncio.to_thread(
                _split_audio_to_chunks,
                temp_audio_path,
                settings.WHISPER_CHUNK_DURATION_MS,
            )
        except FileNotFoundError:
            logger.warning("ffprobe/ffmpeg not found locally — skipping client-side chunking, sending whole file to Whisper service")
            chunk_paths = []

        if not chunk_paths:
            # Audio is short enough or ffprobe unavailable — send as-is
            return await _transcribe_single_file(recording_source, whisper_model, whisper_options)

        logger.info(
            f"Split {source_info} into {len(chunk_paths)} chunks "
            f"({settings.WHISPER_CHUNK_DURATION_MS // 1000}s each), transcribing in parallel"
        )

        form_fields = {"model": whisper_model, "whisper_options": whisper_options}

        async with httpx.AsyncClient(
                timeout=httpx.Timeout(settings.DEFAULT_TIMEOUT, connect=settings.CONNECT_TIMEOUT),
                limits=httpx.Limits(
                    max_connections=settings.MAX_CONNECTIONS,
                    max_keepalive_connections=settings.MAX_KEEPALIVE_CONNECTIONS,
                ),
        ) as client:
            # Transcribe chunks in parallel with concurrency limit
            semaphore = asyncio.Semaphore(settings.WHISPER_MAX_PARALLEL_CHUNKS)

            async def _transcribe_with_limit(chunk_path: str) -> Dict[str, Any]:
                async with semaphore:
                    return await _transcribe_single_chunk(chunk_path, form_fields, client)

            chunk_results = await asyncio.gather(
                *[_transcribe_with_limit(cp) for cp in chunk_paths]
            )

        merged = _merge_chunk_results(list(chunk_results), settings.WHISPER_CHUNK_DURATION_MS)
        logger.info(f"Successfully transcribed {source_info} ({len(chunk_paths)} chunks merged)")
        return merged

    except AppException:
        raise

    except FileNotFoundError as e:
        logger.error(f"Audio file not found: {e}")
        raise AppException(ErrorKey.FILE_NOT_FOUND)

    except Exception as e:
        logger.error(f"Unexpected error during chunked transcription: {e}")
        raise AppException(ErrorKey.INTERNAL_ERROR, status_code=500)

    finally:
        _cleanup_temp_files(chunk_paths)
        if is_temp_source and temp_audio_path:
            _cleanup_temp_files([temp_audio_path])


async def _transcribe_single_file(
        recording_source: Union[str, UploadFile],
        whisper_model: str,
        whisper_options: Optional[str],
        ) -> Dict[str, Any]:
    """Original single-file transcription for short audio."""
    source_info = recording_source.filename if isinstance(recording_source, UploadFile) else recording_source

    try:
        async with httpx.AsyncClient(
                timeout=httpx.Timeout(settings.DEFAULT_TIMEOUT, connect=settings.CONNECT_TIMEOUT),
                limits=httpx.Limits(
                        max_connections=settings.MAX_CONNECTIONS,
                        max_keepalive_connections=settings.MAX_KEEPALIVE_CONNECTIONS
                        ),
                ) as client:
            form_fields = {"model": whisper_model, "whisper_options": whisper_options}

            try:
                resp = await _post_with_file(
                        settings.WHISPER_TRANSCRIBE_SERVICE,
                        recording_source,
                        form_fields,
                        client,
                        )
                resp.raise_for_status()

                try:
                    result = resp.json()
                    if not isinstance(result, dict):
                        raise AppException(ErrorKey.ERROR_RESPONSE_FORMAT)
                    elif result.get("error"):
                        logger.error(f"Error in whisper result: {result['error']}")
                        raise AppException(ErrorKey.ERROR_RETURN_WHISPER_SERVICE)

                    logger.info(f"Successfully transcribed {source_info}")
                    return result

                except ValueError as e:
                    logger.warning(f"Failed to parse JSON response: {e}, response:{resp.text}")
                    raise AppException(ErrorKey.ERROR_RESPONSE_FORMAT)

            except httpx.HTTPStatusError as e:
                logger.error(f"HTTP error during transcription: {e.response.status_code} - {e.response.text}")
                raise AppException(ErrorKey.ERROR_RETURN_WHISPER_SERVICE)

            except httpx.TimeoutException:
                logger.error(f"Timeout during transcription of {source_info}")
                raise AppException(ErrorKey.ERROR_TIMEOUT_WHISPER_SERVICE)

            except httpx.ConnectError:
                logger.error(f"Failed to connect to Whisper service at {settings.WHISPER_TRANSCRIBE_SERVICE}")
                raise AppException(ErrorKey.ERROR_CONNECTING_WHISPER_SERVICE)

    except AppException:
        raise

    except Exception as e:
        logger.error(f"Unexpected error during transcription: {e}")
        raise AppException(ErrorKey.INTERNAL_ERROR, status_code=500)
