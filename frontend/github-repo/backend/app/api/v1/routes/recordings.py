import logging
from datetime import datetime
from typing import Annotated, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import FileResponse
from fastapi_injector import Injected

from app.core.config.settings import settings
from app.auth.dependencies import auth, permissions
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.schemas.recording import RecordingRead, RecordingCreate
from app.schemas.question import QuestionCreate
from app.schemas.conversation_transcript import ConversationTranscriptCreate
from app.services.audio import AudioService
from app.core.utils.bi_utils import validate_upload_file_size


logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/analyze_recording", dependencies=[
                   Depends(auth),
                   Depends(permissions("create:analyze_recording"))
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
                   Depends(permissions("create:upload_transcript"))
                   ])
async def process_transcript(
        model: ConversationTranscriptCreate, service: AudioService = Injected(AudioService)
        ):
    analysis_data = await service.process_transcript(model)
    return {"message": "Transcript processed and saved", "analysis_data": analysis_data}


@router.get("/recordings/{recording_id}", dependencies=[
                   Depends(auth),
                   Depends(permissions("read:recording"))
                   ])
def get_recording(recording_id: UUID, service: AudioService = Injected(AudioService)):
    processed_recording_data = service.fetch_processed_recording(recording_id)
    return processed_recording_data, 200


@router.post("/ask_question", dependencies=[
    Depends(auth),
    Depends(permissions("create:ask_question"))
    ])
async def ask_question(question_model: QuestionCreate, service: AudioService = Injected(AudioService)):
    answer = await service.ask_question_to_model(question_model)
    return {"answer": answer}


@router.get("/files/{rec_id}", dependencies=[
    Depends(auth),
    Depends(permissions("read:files"))
    ])
async def serve_file(rec_id: UUID, service: AudioService = Injected(AudioService)):
    """Serve the saved recording file based on filename."""
    recording_data: RecordingRead = await service.find_recording_by_id(rec_id)

    return FileResponse(recording_data.file_path)


@router.get("/metrics", dependencies=[
    Depends(auth),
    Depends(permissions("read:metrics"))
    ])
async def get_metrics(service: AudioService = Injected(AudioService)):
    return await service.fetch_and_calculate_metrics()

# @router.post("/transcribe_no_save")
# async def transcribe_no_save(file: UploadFile, service: RecordingService = Depends()):
#     # TODO Fabio/Emiliano endpoint remove in the future or add security
#     result = await service.generate_transcript_from_audio_no_save(file)
#     return result
