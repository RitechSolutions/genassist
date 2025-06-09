import os
from uuid import UUID
import json
from datetime import datetime, timezone
import logging
from typing import Dict, List, Optional, Tuple
from fastapi import Depends
from app.auth.utils import get_current_operator_id, get_current_user_id, is_current_user_supervisor_or_admin
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.core.utils.bi_utils import calculate_duration_from_transcript, calculate_speaker_ratio_from_segments
from app.core.utils.enums.conversation_status_enum import ConversationStatus
from app.core.utils.enums.conversation_type_enum import ConversationType
from app.core.utils.enums.transcript_message_type import TranscriptMessageType
from app.db.models.conversation import ConversationAnalysisModel, ConversationModel
from app.db.seed.seed_data_config import seed_test_data
from app.db.utils.sql_alchemy_utils import null_unloaded_attributes
from app.repositories.conversations import ConversationRepository
from app.schemas.conversation import ConversationCreate
from app.schemas.conversation_analysis import ConversationAnalysisRead
from app.schemas.conversation_transcript import ConversationTranscriptCreate, InProgConvTranscrUpdate, \
    TranscriptSegmentInput
from app.schemas.filter import ConversationFilter
from app.services.conversation_analysis import ConversationAnalysisService
from app.services.gpt_kpi_analyzer import GptKpiAnalyzer
from app.services.llm_analysts import LlmAnalystService
from app.services.operator_statistics import OperatorStatisticsService
from app.services.zendesk import ZendeskClient


def get_messages_string_by_type(transcription: str, message_type: TranscriptMessageType):
    transcript_dicts: list[Dict] = json.loads(transcription)
    filtered_segments = [segment for segment in transcript_dicts if segment['type'] == message_type.value]
    return json.dumps(filtered_segments)

logger = logging.getLogger(__name__)

class ConversationService:
    def __init__(self, conversation_repo: ConversationRepository = Depends(), gpt_kpi_analyzer_service:
    GptKpiAnalyzer = Depends(), conversation_analysis_service: ConversationAnalysisService = Depends(),
                 operator_statistics_service: OperatorStatisticsService = Depends(),
                 llm_analyst_service: LlmAnalystService = Depends(), ):
        self.conversation_repo = conversation_repo
        self.gpt_kpi_analyzer_service = gpt_kpi_analyzer_service
        self.conversation_analysis_service = conversation_analysis_service
        self.operator_statistics_service = operator_statistics_service
        self.llm_analyst_service = llm_analyst_service

    async def save_conversation(self, conversation: ConversationCreate):
        return await self.conversation_repo.save_conversation(conversation)

    async def get_conversation_by_id(self, conversation_id: UUID):
        conversation = await self.conversation_repo.fetch_conversation_by_id(conversation_id)
        if not conversation:
            raise AppException(ErrorKey.CONVERSATION_NOT_FOUND, status_code=404)
        return conversation

    async def get_conversation_by_id_full(self, conversation_id: UUID):
        conversation = await self.conversation_repo.fetch_conversation_by_id_full(conversation_id)
        if not conversation:
            raise AppException(ErrorKey.CONVERSATION_NOT_FOUND, status_code=404)
        return conversation

    async def start_in_progress_conversation(self, model: ConversationTranscriptCreate):
        """
        Creates a new conversation with 'status=in_progress' and partial transcript data
        """
        # Convert the partial segments to JSON
        # agent_ratio, customer_ratio, total_word_count = calculate_speaker_ratio_from_segments(model.messages)
        transcript_string = json.dumps([item.model_dump() for item in model.messages], ensure_ascii=False,
                                       default=str)
        # Build a ConversationCreate object
        new_conv_data = ConversationCreate(
                operator_id=model.operator_id,
                data_source_id=model.data_source_id,
                recording_id=None,
                transcription=transcript_string,
                conversation_date=datetime.now(timezone.utc),
                customer_id=model.customer_id,
                word_count=0,
                customer_ratio=0,
                agent_ratio=0,
                duration=calculate_duration_from_transcript(model.messages),
                status = ConversationStatus.IN_PROGRESS.value,
                conversation_type=ConversationType.PROGRESSIVE.value,
                )

        model = await self.conversation_repo.save_conversation(new_conv_data)
        return model

    async def update_in_progress_conversation(self, conversation_id: UUID,
                                              in_progress_conv_update: InProgConvTranscrUpdate):
        """
        Appends new transcript segments to an existing conversation (still in progress).
        Then performs partial tone check and possible escalation.
        """
        conversation = await self.conversation_repo.fetch_conversation_by_id(conversation_id)
        if not conversation:
            raise AppException(ErrorKey.CONVERSATION_NOT_FOUND, status_code=404)

        if conversation.status == ConversationStatus.FINALIZED.value:
            raise AppException(ErrorKey.CONVERSATION_FINALIZED)

        transcript_dict, transcript_json_str = await self._extend_transcript(conversation, in_progress_conv_update.messages)
        conversation.transcription = transcript_json_str

        #  Calculate word counts
        message_type_transcript_segments = [TranscriptSegmentInput.model_validate(segment) for segment in transcript_dict
                                            if segment['type'] == TranscriptMessageType.MESSAGE.value]
        agent_ratio, customer_ratio, total_word_count = calculate_speaker_ratio_from_segments(message_type_transcript_segments)
        conversation.agent_ratio = agent_ratio
        conversation.customer_ratio = customer_ratio
        conversation.word_count = total_word_count

        # Calculate duration from transcript segments
        conversation_duration = calculate_duration_from_transcript(message_type_transcript_segments)
        conversation.duration = conversation_duration

        # Set user id since we are in socket connection:
        conversation.updated_by = get_current_user_id()
        conversation = await self.conversation_repo.update_conversation(conversation)

        # Perform partial tone check
        conversation = await self._analyze_in_progress_tone_and_mark(conversation, transcript_json_str,
                                                                     llm_analyst_id=in_progress_conv_update.llm_analyst_id)
        null_unloaded_attributes(conversation)
        return conversation


    async def _extend_transcript(self, conversation, messages: list[TranscriptSegmentInput]):
        transcript_dict = []
        if conversation.transcription:
            try:
                transcript_dict = json.loads(conversation.transcription)
            except json.JSONDecodeError:
                raise AppException(ErrorKey.TRANSCRIPT_ERROR_PARSING, status_code=500)
        # Append the new segments
        new_segments = [seg.model_dump() for seg in messages]
        transcript_dict.extend(new_segments)
        new_transcript_json_string = json.dumps(transcript_dict, ensure_ascii=False, default=str)
        return transcript_dict, new_transcript_json_string

    def _validate_in_progress(self, conversation):
        if conversation.status == ConversationStatus.FINALIZED.value:
            raise AppException(ErrorKey.CONVERSATION_FINALIZED)
        if conversation.status == ConversationStatus.TAKE_OVER.value:
            raise AppException(ErrorKey.CONVERSATION_TAKEN_OVER)

    async def finalize_in_progress_conversation(
        self,
        llm_analyst_id: UUID,
        conversation_id: UUID
    ) -> ConversationAnalysisRead:
        """
        Switch conversation's status to 'finalized'
        so it won't be updated further.
        """
        conversation = await self.conversation_repo.fetch_conversation_by_id(conversation_id)
        if not conversation:
            raise AppException(ErrorKey.CONVERSATION_NOT_FOUND)

        if conversation.status == ConversationStatus.FINALIZED.value:
            raise AppException(ErrorKey.CONVERSATION_FINALIZED)

        # Mark as finalized
        conversation.status = ConversationStatus.FINALIZED.value
        saved_conversation = await self.conversation_repo.update_conversation(conversation)

        # Run GPT analysis
        if not llm_analyst_id:
            llm_analyst_id = seed_test_data.llm_analyst_kpi_analyzer_id

        llm_analyst = await self.llm_analyst_service.get_by_id(llm_analyst_id)

        message_type_segments = get_messages_string_by_type(
            conversation.transcription, TranscriptMessageType.MESSAGE
        )

        if message_type_segments == "[]":
            raise ValueError(f"Transcription resulted in empty segment! Original: {conversation.transcription}")

        gpt_analysis = await self.gpt_kpi_analyzer_service.analyze_transcript(
            message_type_segments, llm_analyst=llm_analyst
        )

        conversation_analysis = await self.conversation_analysis_service.create_conversation_analysis(
            gpt_analysis,
            llm_analyst_id,
            saved_conversation.id
        )

        # Update operator statistics
        await self.operator_statistics_service.update_from_analysis(
            conversation_analysis,
            conversation.operator_id,
            saved_conversation.duration
        )

        store_in_zendesk = os.getenv("STORE_CONVERSATIONS_IN_ZENDESK", "false").lower() == "true"
        if store_in_zendesk:
            await self.store_zendesk_analysis(saved_conversation, conversation_analysis)

        return ConversationAnalysisRead.model_validate(conversation_analysis)

    async def store_zendesk_analysis(self, saved_conversation: ConversationModel, conversation_analysis: ConversationAnalysisModel):
        # Create or update a Zendesk ticket here
        zendesk = ZendeskClient()

        # Pull out the detailed fields for the ticket comment
        topic = conversation_analysis.topic or ""
        summary = conversation_analysis.summary or ""
        resolution_rate = conversation_analysis.resolution_rate or 0
        customer_satisfaction = conversation_analysis.customer_satisfaction or 0
        service_quality = conversation_analysis.quality_of_service or 0

        # Helper to convert 0–10 scale to percentage
        def to_percent(value: int) -> int:
            return int((value / 10) * 100)

        if saved_conversation.zendesk_ticket_id:
            comment_body = (
                "Ticket Closed\n"
                f"🔹 Topic: {topic}\n"
                f"🔹 Summary: {summary}\n"
                f"🔹 Resolution Rate: {resolution_rate}%\n"
                f"🔹 Customer Satisfaction: {to_percent(customer_satisfaction)}%\n"
                f"🔹 Service Quality: {to_percent(service_quality)}%\n\n"
                "For any follow‐up, please contact the customer by email "
                "and ask about any remaining concerns."
            )
            await zendesk.update_ticket(
                ticket_id=saved_conversation.zendesk_ticket_id,
                comment=comment_body
            )
        else:
            subject = f"GenAssist Conversation {saved_conversation.id} – Needs review"
            description = (
                "GenAssist conversation was finalized. Please review metrics.\n\n"
                f"🔹 Topic: {topic}\n"
                f"🔹 Summary: {summary}\n"
                f"🔹 Resolution Rate: {resolution_rate}%\n"
                f"🔹 Customer Satisfaction: {to_percent(customer_satisfaction)}%\n"
                f"🔹 Service Quality: {to_percent(service_quality)}%\n"
            )
            requester_email = "customer@example.com"

            new_ticket_id = await zendesk.create_ticket(
                subject=subject,
                description=description,
                requester_email=requester_email,
                conversation_id=str(saved_conversation.id),
                tags=["genassist"]
            )

            if new_ticket_id:
                # Save that new ticket ID into `ConversationModel.zendesk_ticket_id`
                saved_conversation.zendesk_ticket_id = new_ticket_id
                await self.conversation_repo.update_conversation(saved_conversation)
                
    async def _analyze_in_progress_tone_and_mark(
            self,
            conversation: ConversationModel,
            transcript: str,
            llm_analyst_id: Optional[UUID] = None,
            ):

        #  Run GPT analysis
        if not llm_analyst_id:
            llm_analyst_id = seed_test_data.llm_analyst_kpi_analyzer_id

        llm_analyst = await self.llm_analyst_service.get_by_id(llm_analyst_id)
        analysis_result = await self.gpt_kpi_analyzer_service.partial_hostility_analysis(transcript, llm_analyst=llm_analyst)

        # This returns something like: {"sentiment": "negative", "hostile_score": 85}
        hostile_score = analysis_result["hostile_score"]


        conversation.in_progress_hostility_score = hostile_score

        return await self.conversation_repo.update_conversation(conversation)

    async def supervisor_takeover_conversation(self, conversation_id: UUID):
        conversation = await self.conversation_repo.fetch_conversation_by_id(conversation_id)
        self._validate_in_progress(conversation)
        _, transcript_json_str = await self._extend_transcript(conversation,
                                                                             [TranscriptSegmentInput(
                                                                                     create_time=datetime.now(),
                                                                                     start_time=0,
                                                                                     end_time=0,
                                                                                     speaker="",
                                                                                     text="",
                                                                                     type="takeover"
                                                                                     )])

        # Assign the supervisor
        conversation.transcription = transcript_json_str
        conversation.supervisor_id = get_current_user_id()
        conversation.status = ConversationStatus.TAKE_OVER.value
        conversation = await self.conversation_repo.update_conversation(conversation)
        null_unloaded_attributes(conversation)
        return conversation

    async def get_conversations(self, conversation_filter: ConversationFilter):

        # If not supervisor or admin, you can see only your conversations
        if not is_current_user_supervisor_or_admin():
            # if not admin/super and not operator, can't see any conversations
            if not get_current_operator_id():
                raise AppException(error_key=ErrorKey.OPERATOR_NOT_FOUND)
            # if operator exists we filter by the operator id
            conversation_filter.operator_id = get_current_operator_id()



        models = await self.conversation_repo.fetch_conversations_with_recording(conversation_filter)
        return models


    async def get_stale_conversations(self, cutoff_time: datetime):
        models = await self.conversation_repo.get_stale_conversations(cutoff_time)
        return models

    async def delete_conversation(self, conversation_id: UUID):
        conversation = await self.conversation_repo.fetch_conversation_by_id(conversation_id)
        if not conversation:
            raise AppException(ErrorKey.CONVERSATION_NOT_FOUND)
        await self.conversation_repo.delete_conversation(conversation)
        return conversation

    async def cleanup_stale_conversations(self, cutoff_time: datetime):
        stale_conversations = await self.get_stale_conversations(cutoff_time)
        print(f"Got {len(stale_conversations)} stale conversations for cutoff time {cutoff_time}")
        
        deleted_count = 0
        finalized_count = 0
        failed_count = 0

        # Process the stale conversations
        for conversation in stale_conversations:
            transcript = json.loads(conversation.transcription)
            if len(transcript) < 3:
                await self.delete_conversation(conversation.id)
                deleted_count += 1
                logger.info(f"Deleted stale conversation {conversation.id} (last updated: {conversation.updated_at})")
            else:
                try:
                    # Use the default KPI analyzer for finalization
                    await self.finalize_in_progress_conversation(
                        llm_analyst_id=seed_test_data.llm_analyst_kpi_analyzer_id,
                        conversation_id=conversation.id
                    )
                    finalized_count += 1
                    logger.info(f"Finalized conversation {conversation.id} (last updated: {conversation.updated_at})")
                except Exception as e:
                    logger.error(f"Failed to finalize conversation {conversation.id}: {str(e)}")
                    failed_count += 1

        return {
            "deleted_count": deleted_count,
            "finalized_count": finalized_count,
            "failed_count": failed_count
        }

    async def get_topics_count(self) -> Dict[str, int]:
        raw: List[Tuple[str, int]] = await self.conversation_repo.get_topics_count()

        topic_counts: Dict[str, int] = {}
        total_count = 0

        for topic, count in raw:
            normalized_topic = topic or "Other"
            topic_counts[normalized_topic] = count
            total_count += count

        return {
        "total": total_count,
        "details": topic_counts
    }