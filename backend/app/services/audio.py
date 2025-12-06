import datetime
import json
import shutil
import uuid
from pathlib import Path
from fastapi import UploadFile, Depends
from fastapi_injector import Injected
from injector import inject

from app.core.config.settings import settings
from app.core.utils.enums.conversation_type_enum import ConversationType
from app.db.models.llm import LlmAnalystModel
from app.db.seed.seed_data_config import seed_test_data
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.repositories.recordings import RecordingsRepository
from app.schemas.conversation import ConversationCreate
from app.schemas.conversation_transcript import (
    ConversationTranscriptCreate,
    TranscriptSegmentInput,
)
from app.schemas.question import QuestionCreate
from app.schemas.recording import RecordingCreate
from app.services.conversation_analysis import ConversationAnalysisService
from app.services.conversations import ConversationService
from app.services.gpt_kpi_analyzer import GptKpiAnalyzer
from app.services.gpt_questions import QuestionAnswerer
from app.services.gpt_speaker_separator import SpeakerSeparator
from app.services.llm_analysts import LlmAnalystService
from app.services.operator_statistics import OperatorStatisticsService
from app.services.operators import OperatorService
from app.services.transcription import transcribe_audio_whisper
from app.core.utils.bi_utils import (
    allowed_file,
    calculate_duration_from_transcript,
    calculate_speaker_ratio_from_segments,
    extract_transcript_from_whisper_model,
)
from app.core.utils.transcript_utils import transcript_messages_to_json

from app.services.GoogleTranscribeService import GoogleTranscribeService


@inject
class AudioService:
    def __init__(
        self,
        operator_service: OperatorService,
        recording_repo: RecordingsRepository,
        conversation_service: ConversationService,
        conversation_analysis_service: ConversationAnalysisService,
        operator_statistics_service: OperatorStatisticsService,
        speaker_separator_service: SpeakerSeparator,
        gpt_kpi_analyzer_service: GptKpiAnalyzer,
        gpt_question_answerer_service: QuestionAnswerer,
        llm_analyst_service: LlmAnalystService,
    ):
        self.recording_repo = recording_repo
        self.conversation_service = conversation_service
        self.conversation_analysis_service = conversation_analysis_service
        self.operator_statistics_service = operator_statistics_service
        self.speaker_separator_service = speaker_separator_service
        self.gpt_kpi_analyzer_service = gpt_kpi_analyzer_service
        self.gpt_question_answerer_service = gpt_question_answerer_service
        self.operator_service = operator_service
        self.llm_analyst_service = llm_analyst_service

    async def fetch_processed_recording(self, recording_id):
        return await self.recording_repo.find_by_id(recording_id)

    async def ask_question_to_model(self, question_model: QuestionCreate) -> str:
        conversation_id = question_model.conversation_id
        question = question_model.question

        # Fetch transcript from DB
        conversation = await self.conversation_service.get_conversation_by_id(
            conversation_id, include_messages=True
        )
        if not conversation:
            raise AppException(ErrorKey.TRANSCRIPT_NOT_FOUND, status_code=404)

        transcript_json = None
        transcription_value = conversation.transcription

        if isinstance(transcription_value, str) and transcription_value.strip():
            placeholder = "moved to transcript_messages table"
            if transcription_value.strip().lower() != placeholder:
                transcript_json = transcription_value

        if not transcript_json and getattr(conversation, "messages", None):
            transcript_json = transcript_messages_to_json(
                conversation.messages, exclude_fields={"feedback"}
            )

        if not transcript_json:
            raise AppException(ErrorKey.TRANSCRIPT_NOT_FOUND, status_code=404)

        # Validate JSON structure before proceeding
        try:
            json.loads(transcript_json)
        except json.JSONDecodeError:
            raise AppException(ErrorKey.TRANSCRIPT_PARSE_ERROR)

        # Ask GPT the question
        return self.gpt_question_answerer_service.answer_question(
            transcript_json, question
        )

    async def fetch_and_calculate_metrics(self):
        return await self.recording_repo.get_metrics()

    async def _separate_speakers_gpt(
        self, transcription_object, llm_analyst: LlmAnalystModel
    ) -> list[dict]:
        transcript_data = extract_transcript_from_whisper_model(transcription_object)
        transcript_string = json.dumps(transcript_data)
        return await self.speaker_separator_service.separate(
            transcript_string, llm_analyst
        )

    async def process_recording(self, file: UploadFile, model: RecordingCreate):
        if not allowed_file(file.filename):
            raise AppException(
                error_key=ErrorKey.FILE_TYPE_NOT_ALLOWED, status_code=400
            )

        operator = await self.operator_service.get_by_id(model.operator_id)
        if not operator:
            raise AppException(error_key=ErrorKey.OPERATOR_NOT_FOUND)

        model.original_filename = file.filename
        rec_path, saved_recording = await self._save_recording(file, model)

        # Transcribe audio
        whisper_transcription_object = await transcribe_audio_whisper(
            rec_path, model.transcription_model_name
        )

        # Separate speakers with GPT
        if not model.llm_analyst_speaker_separator_id:
            model.llm_analyst_speaker_separator_id = (
                seed_test_data.llm_analyst_speaker_separator_id
            )

        llm_analyst_speaker_separator = await self.llm_analyst_service.get_by_id(
            model.llm_analyst_speaker_separator_id
        )

        separated_speakers: list[dict] = await self._separate_speakers_gpt(
            whisper_transcription_object, llm_analyst=llm_analyst_speaker_separator
        )

        transcript_segments: list[TranscriptSegmentInput] = [
            TranscriptSegmentInput(**item) for item in separated_speakers
        ]

        agent_ratio, customer_ratio, total_word_count = (
            calculate_speaker_ratio_from_segments(transcript_segments)
        )

        # Calculate duration from transcript segments
        duration = calculate_duration_from_transcript(transcript_segments)

        separated_speakers_str = json.dumps(separated_speakers, ensure_ascii=False)

        conversation_data = ConversationCreate(
            operator_id=model.operator_id,
            data_source_id=model.data_source_id,
            recording_id=saved_recording.id,
            transcription="moved to transcript_messages table",
            conversation_date=model.recording_date,
            customer_id=model.customer_id,
            word_count=total_word_count,
            customer_ratio=customer_ratio,
            agent_ratio=agent_ratio,
            duration=duration,
            conversation_type=ConversationType.AUDIO.value,
        )

        saved_conversation = await self.conversation_service.save_conversation(
            conversation_data
        )
        await self.conversation_service.save_new_messages(
            saved_conversation.id, transcript_segments, next_sequence=0
        )

        # Run Kpi analysis with GPT
        if not model.llm_analyst_kpi_analyzer_id:
            model.llm_analyst_kpi_analyzer_id = (
                seed_test_data.llm_analyst_kpi_analyzer_id
            )

        llm_analyst_kpi_analyzer = await self.llm_analyst_service.get_by_id(
            model.llm_analyst_kpi_analyzer_id
        )

        gpt_analysis = await self.gpt_kpi_analyzer_service.analyze_transcript(
            separated_speakers_str, llm_analyst=llm_analyst_kpi_analyzer
        )

        saved_conversation_analysis = (
            await self.conversation_analysis_service.create_conversation_analysis(
                gpt_analysis, model.llm_analyst_kpi_analyzer_id, saved_conversation.id
            )
        )

        await self.operator_statistics_service.update_from_analysis(
            saved_conversation_analysis, model.operator_id, duration
        )

        return saved_conversation_analysis

    async def _save_recording(self, file, recording_create):
        # Save the file and get its path
        rec_path = await self._save_recording_in_path(
            file, recording_create.operator_id
        )
        # Save metadata to the database
        saved_recording = await self.recording_repo.save_recording(
            rec_path, recording_create
        )
        return rec_path, saved_recording

    async def _save_recording_in_path(
        self, recording: UploadFile, operator_id: uuid.UUID
    ) -> str:
        """Save a recording file to the server and return the file path."""

        # Ensure the operator-specific directory exists
        operator_dir = Path(settings.RECORDINGS_DIR) / str(operator_id)
        operator_dir.mkdir(parents=True, exist_ok=True)  # Correct method call

        # Generate a unique filename
        timestamp = datetime.datetime.now(datetime.timezone.utc).strftime(
            "%Y%m%d_%H%M%S"
        )
        file_extension = recording.filename.split(".")[-1]
        unique_filename = f"{uuid.uuid4()}_{timestamp}.{file_extension}"
        file_path = operator_dir / unique_filename

        # Save the file to disk
        with file_path.open("wb") as buffer:
            shutil.copyfileobj(recording.file, buffer)

        return str(file_path)  # Return the saved file path

    async def process_transcript(self, model: ConversationTranscriptCreate):

        operator = await self.operator_service.get_by_id(model.operator_id)
        if not operator:
            raise AppException(error_key=ErrorKey.OPERATOR_NOT_FOUND)

        #  Calculate word counts
        agent_ratio, customer_ratio, total_word_count = (
            calculate_speaker_ratio_from_segments(model.messages)
        )

        # Calculate duration from transcript segments
        conversation_duration = calculate_duration_from_transcript(model.messages)

        transcript_string = json.dumps(
            [item.model_dump() for item in model.messages],
            ensure_ascii=False,
            default=str,
        )

        #  Save conversation
        conversation_data = ConversationCreate(
            operator_id=model.operator_id,
            data_source_id=model.data_source_id,
            recording_id=None,  # No recording file here
            transcription="moved to transcript_messages table",
            conversation_date=model.recorded_at,
            customer_id=model.customer_id,
            word_count=total_word_count,
            customer_ratio=customer_ratio,
            agent_ratio=agent_ratio,
            duration=conversation_duration,
            conversation_type=ConversationType.TRANSCRIPT.value,
        )

        saved_conversation = await self.conversation_service.save_conversation(
            conversation_data
        )
        await self.conversation_service.save_new_messages(
            saved_conversation.id, model.messages, next_sequence=0
        )

        #  Run GPT analysis
        if not model.llm_analyst_id:
            model.llm_analyst_id = seed_test_data.llm_analyst_kpi_analyzer_id

        llm_analyst = await self.llm_analyst_service.get_by_id(model.llm_analyst_id)

        gpt_analysis = await self.gpt_kpi_analyzer_service.analyze_transcript(
            transcript_string, llm_analyst=llm_analyst
        )

        conservation_analysis = (
            await self.conversation_analysis_service.create_conversation_analysis(
                gpt_analysis, model.llm_analyst_id, saved_conversation.id
            )
        )

        # Update operator statistics
        await self.operator_statistics_service.update_from_analysis(
            conservation_analysis, model.operator_id, conversation_duration
        )

        return conservation_analysis

    async def find_recording_by_id(self, rec_id):
        return await self.recording_repo.find_by_id(rec_id)

    async def recording_exists(
        self, original_filename: str, data_source_id: uuid.UUID
    ) -> bool:
        return await self.recording_repo.recording_exists(
            original_filename, data_source_id
        )

    ####################### CHIRP/Google Transcirbe
    async def process_recording_chirp(
        self,
        file: UploadFile,
        model: RecordingCreate,
        chirp_transcriber_service: GoogleTranscribeService,
    ):
        if not allowed_file(file.filename):
            raise AppException(
                error_key=ErrorKey.FILE_TYPE_NOT_ALLOWED, status_code=400
            )

        operator = await self.operator_service.get_by_id(model.operator_id)
        if not operator:
            raise AppException(error_key=ErrorKey.OPERATOR_NOT_FOUND)

        model.original_filename = file.filename
        rec_path, saved_recording = await self._save_recording(file, model)

        # Transcribe audio
        transcribed_result = chirp_transcriber_service.transcribe_long_audio(
            content=file.file.getvalue(), file_name=file.filename
        )
        final_transcribed = chirp_transcriber_service.get_merged_transcripts(
            transcribed_result
        )
        # whisper_transcription_object = await transcribe_audio_whisper(rec_path, model.transcription_model_name)

        # Separate speakers with GPT
        if not model.llm_analyst_speaker_separator_id:
            model.llm_analyst_speaker_separator_id = (
                seed_test_data.llm_analyst_speaker_separator_id
            )

        llm_analyst_speaker_separator = await self.llm_analyst_service.get_by_id(
            model.llm_analyst_speaker_separator_id
        )

        separated_speakers: list[dict] = await self._separate_speakers_gpt(
            final_transcribed, llm_analyst=llm_analyst_speaker_separator
        )

        transcript_segments: list[TranscriptSegmentInput] = [
            TranscriptSegmentInput(**item) for item in separated_speakers
        ]

        agent_ratio, customer_ratio, total_word_count = (
            calculate_speaker_ratio_from_segments(transcript_segments)
        )

        # Calculate duration from transcript segments
        duration = calculate_duration_from_transcript(transcript_segments)

        separated_speakers_str = json.dumps(separated_speakers, ensure_ascii=False)

        conversation_data = ConversationCreate(
            operator_id=model.operator_id,
            data_source_id=model.data_source_id,
            recording_id=saved_recording.id,
            transcription="moved to transcript_messages table",
            conversation_date=model.recording_date,
            customer_id=model.customer_id,
            word_count=total_word_count,
            customer_ratio=customer_ratio,
            agent_ratio=agent_ratio,
            duration=duration,
            conversation_type=ConversationType.AUDIO.value,
        )

        saved_conversation = await self.conversation_service.save_conversation(
            conversation_data
        )
        await self.conversation_service.save_new_messages(
            saved_conversation.id, transcript_segments, next_sequence=0
        )

        # Run Kpi analysis with GPT
        if not model.llm_analyst_kpi_analyzer_id:
            model.llm_analyst_kpi_analyzer_id = (
                seed_test_data.llm_analyst_kpi_analyzer_id
            )

        llm_analyst_kpi_analyzer = await self.llm_analyst_service.get_by_id(
            model.llm_analyst_kpi_analyzer_id
        )

        gpt_analysis = await self.gpt_kpi_analyzer_service.analyze_transcript(
            separated_speakers_str, llm_analyst=llm_analyst_kpi_analyzer
        )

        saved_conversation_analysis = (
            await self.conversation_analysis_service.create_conversation_analysis(
                gpt_analysis, model.llm_analyst_kpi_analyzer_id, saved_conversation.id
            )
        )

        await self.operator_statistics_service.update_from_analysis(
            saved_conversation_analysis, model.operator_id, duration
        )

        return saved_conversation_analysis
