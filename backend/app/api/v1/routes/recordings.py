import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Annotated, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi_injector import Injected
from app.core.permissions.constants import Permissions as P
from app.core.config.settings import settings
from app.auth.dependencies import auth, permissions
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.schemas.recording import RecordingRead, RecordingCreate
from app.schemas.question import QuestionCreate
from app.schemas.conversation_transcript import ConversationTranscriptCreate
from app.services.audio import AudioService
from app.core.utils.bi_utils import validate_upload_file_size


def get_safe_file_path(file_path: str, allowed_directory: str) -> str:
    """
    Sanitize and validate that a file path is within an allowed directory.
    Prevents path traversal attacks by normalizing, validating, and reconstructing the path.

    Args:
        file_path: The file path to validate
        allowed_directory: The directory the file must be within

    Returns:
        A sanitized absolute path string that is safe to use

    Raises:
        HTTPException: If the path escapes the allowed directory or contains traversal
    """
    # Normalize the input path to catch traversal attempts
    normalized_path = os.path.normpath(file_path)

    # Check for path traversal after normalization
    if ".." in normalized_path:
        raise HTTPException(
            status_code=400,
            detail="Invalid file path"
        )

    resolved_file = Path(normalized_path).resolve()
    resolved_dir = Path(allowed_directory).resolve()

    # Validate the file is within the allowed directory
    try:
        relative_path = resolved_file.relative_to(resolved_dir)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid file path"
        )

    # Reconstruct the path from known-safe base directory and validated relative path
    # This breaks the taint chain by creating a new path from safe components
    safe_absolute_path = resolved_dir / relative_path

    if not safe_absolute_path.exists():
        raise HTTPException(
            status_code=404,
            detail="File not found"
        )

    # Return the reconstructed safe absolute path as a string
    return str(safe_absolute_path)


logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/analyze_recording", dependencies=[
                   Depends(auth),
                   Depends(permissions(P.Recording.CREATE_ANALYZE))
                   ])
async def analyze_audio(
        operator_id: Annotated[UUID, Form(...)],
        recorded_at: Annotated[str, Form(...)],
        data_source_id: Annotated[UUID|None, Form(...)] = None,
        transcription_model_name: Annotated[str, Form(...)] = settings.DEFAULT_WHISPER_MODEL,
        llm_analyst_speaker_separator_id: Annotated[UUID|None, Form(...)] = None,
        llm_analyst_kpi_analyzer_id: Annotated[UUID|None, Form(...)] = None,
        customer_id: Annotated[Optional[UUID|None], Form()] = None,
        file: UploadFile = File(...),
        service: AudioService = Injected(AudioService),
        ):
    await validate_upload_file_size(file, settings.MAX_CONTENT_LENGTH)
    # Convert recorded_at from string to datetime
    try:
        recorded_at_dt = datetime.strptime(recorded_at, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        raise AppException(error_key=ErrorKey.INVALID_RECORDED_AT)

    metadata = RecordingCreate(
            operator_id=operator_id,
            transcription_model_name=transcription_model_name,
            llm_analyst_speaker_separator_id=llm_analyst_speaker_separator_id,
            llm_analyst_kpi_analyzer_id=llm_analyst_kpi_analyzer_id,
            recorded_at=recorded_at_dt,
            data_source_id=data_source_id,
            customer_id=customer_id,
            )

    return await service.process_recording(file, metadata)


@router.post("/upload_transcript", dependencies=[
                   Depends(auth),
                   Depends(permissions(P.Recording.CREATE_UPLOAD_TRANSCRIPT))
                   ])
async def process_transcript(
        model: ConversationTranscriptCreate, service: AudioService = Injected(AudioService)
        ):
    analysis_data = await service.process_transcript(model)
    return {"message": "Transcript processed and saved", "analysis_data": analysis_data}


@router.get("/recordings/{recording_id}", dependencies=[
                   Depends(auth),
                   Depends(permissions(P.Recording.READ))
                   ])
def get_recording(recording_id: UUID, service: AudioService = Injected(AudioService)):
    processed_recording_data = service.fetch_processed_recording(recording_id)
    return processed_recording_data, 200


@router.post("/ask_question", dependencies=[
    Depends(auth),
    Depends(permissions(P.Recording.CREATE_ASK_QUESTION))
    ])
async def ask_question(question_model: QuestionCreate, service: AudioService = Injected(AudioService)):
    answer = await service.ask_question_to_model(question_model)
    return {"answer": answer}


@router.get("/files/{rec_id}", dependencies=[
    Depends(auth),
    Depends(permissions(P.Recording.READ_FILES))
    ])
async def serve_file(rec_id: UUID, service: AudioService = Injected(AudioService)):
    """Serve the saved recording file based on filename."""
    recording_data: RecordingRead = await service.find_recording_by_id(rec_id)

    # Sanitize and validate file path to prevent path traversal attacks
    safe_path = get_safe_file_path(
        recording_data.file_path,
        settings.RECORDINGS_DIR
    )

    # Final guard: verify path starts with allowed directory before serving
    recordings_dir = str(Path(settings.RECORDINGS_DIR).resolve())
    if not safe_path.startswith(recordings_dir):
        raise HTTPException(status_code=400, detail="Invalid file path")

    return FileResponse(safe_path)


@router.get("/metrics", dependencies=[
    Depends(auth),
    Depends(permissions(P.Recording.READ_METRICS))
    ])
async def get_metrics(service: AudioService = Injected(AudioService)):
    try:
        return await service.fetch_and_calculate_metrics()
    except Exception as e:
        logger.error(f"Error fetching metrics: {e}")
        return {"error": "Error fetching metrics"}

# @router.post("/transcribe_no_save")
# async def transcribe_no_save(file: UploadFile, service: RecordingService = Depends()):
#     # TODO Fabio/Emiliano endpoint remove in the future or add security
#     result = await service.generate_transcript_from_audio_no_save(file)
#     return result
