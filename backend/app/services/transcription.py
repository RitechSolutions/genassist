import logging
import aiofiles
import httpx
import mimetypes
from typing import Any, Dict, Optional, Union
from pathlib import Path
from starlette.datastructures import UploadFile
from app.core.config.settings import settings
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException


logger = logging.getLogger(__name__)


def _guess_mime(path: str) -> str:
    """Guess MIME type for a file path.

    Args:
        path: File path to guess MIME type for

    Returns:
        MIME type string, defaults to application/octet-stream if unknown
    """
    mt, _ = mimetypes.guess_type(path)
    return mt or "application/octet-stream"


async def _post_with_file(
        url: str,
        file_source: Union[str, UploadFile],
        form_fields: Dict[str, Any],
        client: httpx.AsyncClient,
        ) -> httpx.Response:
    """Post a file to a URL with form fields.

    Args:
        url: Target URL
        file_source: Path to file to upload or UploadFile object
        form_fields: Additional form data
        client: HTTP client to use

    Returns:
        HTTP response

    Raises:
        FileNotFoundError: If file doesn't exist (for file paths)
        httpx.HTTPError: If HTTP request fails
    """
    try:
        if isinstance(file_source, UploadFile):
            # Handle UploadFile - stream directly to httpx
            await file_source.seek(0)  # Reset file pointer to beginning
            filename = file_source.filename or "upload"
            mime = file_source.content_type or _guess_mime(filename)

            logger.debug(f"Streaming UploadFile {filename} with MIME type {mime}")

            files = {"file": (filename, file_source.file, mime)}
            return await client.post(url, data=form_fields, files=files)

        else:
            # Handle file path string
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


async def transcribe_audio_whisper(
        recording_source: Union[str, UploadFile],
        whisper_model: Optional[str] = settings.DEFAULT_WHISPER_MODEL,
        whisper_options: Optional[str] = None,
        ) -> Dict[str, Any]:
    """Transcribe audio using Whisper service.

    Args:
        recording_source: Path to audio file or UploadFile object to transcribe
        whisper_model: Whisper model to use (defaults to 'small')
        whisper_options: Additional options for Whisper

    Returns:
        Dictionary containing transcription result or error information
    """
    if whisper_model is None:
        whisper_model = settings.DEFAULT_WHISPER_MODEL

    source_info = recording_source.filename if isinstance(recording_source, UploadFile) else recording_source
    logger.info(f"Starting transcription for {source_info} using model {whisper_model}, with options {whisper_options}")

    try:
        async with httpx.AsyncClient(
                timeout=httpx.Timeout(settings.DEFAULT_TIMEOUT, connect=settings.CONNECT_TIMEOUT),
                limits=httpx.Limits(
                        max_connections=settings.MAX_CONNECTIONS,
                        max_keepalive_connections=settings.MAX_KEEPALIVE_CONNECTIONS
                        ),
                ) as client:
            # Normalize options (model, language, etc.)
            form_fields = {"model": whisper_model, "whisper_options": whisper_options}
            logger.debug(f"Request parameters: {form_fields}")

            try:
                resp = await _post_with_file(
                        settings.WHISPER_TRANSCRIBE_SERVICE,
                        recording_source,
                        form_fields,
                        client,
                        )
                resp.raise_for_status()

                # Validate and parse response
                try:
                    result = resp.json()
                    if not isinstance(result, dict):
                        logger.warning(f"Unexpected response format: {type(result)}")
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

    except FileNotFoundError as e:
        logger.error(f"Audio file not found: {e}")
        raise AppException(ErrorKey.FILE_NOT_FOUND)

    except AppException:
        raise

    except Exception as e:
        logger.error(f"Unexpected error during transcription: {e}")
        raise AppException(ErrorKey.INTERNAL_ERROR, status_code=500)