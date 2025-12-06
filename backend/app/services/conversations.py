import os
from uuid import UUID
import json
from datetime import datetime, timezone
import logging
from typing import Dict, List, Optional, Tuple
from fastapi import Depends
from fastapi_injector import Injected
from injector import inject
from app.auth.utils import (
    get_current_operator_id,
    get_current_user_id,
    is_current_user_supervisor_or_admin,
)
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.core.utils.bi_utils import (
    calculate_duration_from_transcript,
    calculate_incremental_word_counts,
    calculate_speaker_ratio_from_segments,
)
from app.core.utils.enums.conversation_status_enum import ConversationStatus
from app.core.utils.enums.conversation_type_enum import ConversationType
from app.core.utils.enums.message_feedback_enum import Feedback
from app.core.utils.enums.transcript_message_type import TranscriptMessageType
from app.core.utils.transcript_utils import (
    schema_to_transcript_message,
    transcript_messages_to_json,
)
from app.db.models.conversation import ConversationAnalysisModel, ConversationModel
from app.db.models.message_model import TranscriptMessageModel
from app.db.seed.seed_data_config import seed_test_data
from app.db.utils.sql_alchemy_utils import null_unloaded_attributes
from app.repositories.conversations import ConversationRepository
from app.repositories.transcript_message import TranscriptMessageRepository
from app.schemas.conversation import ConversationCreate
from app.schemas.conversation_analysis import ConversationAnalysisRead
from app.schemas.conversation_transcript import (
    ConversationTranscriptCreate,
    InProgConvTranscrUpdate,
    TranscriptSegmentInput,
)
from app.schemas.filter import ConversationFilter
from app.services.conversation_analysis import ConversationAnalysisService
from app.services.gpt_kpi_analyzer import GptKpiAnalyzer
from app.services.llm_analysts import LlmAnalystService
from app.services.operator_statistics import OperatorStatisticsService
from app.services.zendesk import ZendeskClient


logger = logging.getLogger(__name__)


@inject
class ConversationService:
    def __init__(
        self,
        operator_statistics_service: OperatorStatisticsService,
        conversation_repo: ConversationRepository,
        transcript_message_repo: TranscriptMessageRepository,
        gpt_kpi_analyzer_service: GptKpiAnalyzer = Depends(),
        conversation_analysis_service: ConversationAnalysisService = Depends(),
        llm_analyst_service: LlmAnalystService = Injected(LlmAnalystService),
    ):
        self.conversation_repo = conversation_repo
        self.gpt_kpi_analyzer_service = gpt_kpi_analyzer_service
        self.conversation_analysis_service = conversation_analysis_service
        self.operator_statistics_service = operator_statistics_service
        self.llm_analyst_service = llm_analyst_service
        self.transcript_message_repo = transcript_message_repo

    async def save_conversation(self, conversation: ConversationCreate):
        return await self.conversation_repo.save_conversation(conversation)

    async def get_conversation_by_id(
        self,
        conversation_id: UUID,
        raise_not_found: bool = True,
        include_messages: bool = False,
    ):
        conversation = await self.conversation_repo.fetch_conversation_by_id(
            conversation_id,
            include_messages=include_messages,
        )
        if not conversation and raise_not_found:
            raise AppException(ErrorKey.CONVERSATION_NOT_FOUND, status_code=404)
        return conversation

    async def get_conversation_by_id_full(
        self, conversation_id: UUID, conversation_filter: ConversationFilter
    ):
        conversation = await self.conversation_repo.fetch_conversation_by_id_full(
            conversation_id, conversation_filter
        )
        if not conversation:
            raise AppException(ErrorKey.CONVERSATION_NOT_FOUND, status_code=404)
        return conversation

    async def get_conversations_by_customer_id(
        self, customer_id: UUID, raise_not_found: bool = True
    ):
        conversations = await self.conversation_repo.fetch_conversations_by_customer_id(
            customer_id
        )
        if not conversations and raise_not_found:
            raise AppException(ErrorKey.CONVERSATIONS_NOT_FOUND, status_code=404)
        return conversations

    async def start_in_progress_conversation(
        self, model: ConversationTranscriptCreate
    ) -> ConversationModel:
        """
        Creates a new conversation with 'status=in_progress' and saves messages to separate table
        """

        # Create conversation without transcription field
        new_conv_data = ConversationCreate(
            id=model.conversation_id,
            operator_id=model.operator_id,
            data_source_id=model.data_source_id,
            recording_id=None,
            transcription=None,  # No longer storing JSON here
            conversation_date=datetime.now(timezone.utc),
            customer_id=model.customer_id,
            thread_id=model.thread_id,
            word_count=0,
            customer_ratio=0,
            agent_ratio=0,
            duration=0,
            status=ConversationStatus.IN_PROGRESS.value,
            conversation_type=ConversationType.PROGRESSIVE.value,
        )

        conversation = await self.conversation_repo.save_conversation(new_conv_data)

        return conversation

    async def update_in_progress_conversation(
        self, conversation_id: UUID, in_progress_conv_update: InProgConvTranscrUpdate
    ) -> ConversationModel:
        """
        Appends new transcript segments to an existing conversation
        """
        conversation = await self.conversation_repo.fetch_conversation_by_id(
            conversation_id
        )
        if not conversation:
            raise AppException(ErrorKey.CONVERSATION_NOT_FOUND, status_code=404)

        if conversation.status == ConversationStatus.FINALIZED.value:
            raise AppException(ErrorKey.CONVERSATION_FINALIZED)

        # Get only the count for sequence numbering
        next_sequence = await self.transcript_message_repo.get_message_count(
            conversation_id
        )

        # Save new messages
        new_messages = await self.save_new_messages(
            conversation_id, in_progress_conv_update.messages, next_sequence
        )

        # Convert new messages to schema format (filter MESSAGE type only)
        new_segment_inputs = [
            TranscriptSegmentInput(
                create_time=msg.create_time,
                start_time=msg.start_time,
                end_time=msg.end_time,
                speaker=msg.speaker,
                text=msg.text,
                type=msg.type,
            )
            for msg in new_messages
            if msg.type == TranscriptMessageType.MESSAGE.value
        ]

        # Calculate updated word counts and ratios
        agent_ratio, customer_ratio, total_word_count = (
            calculate_incremental_word_counts(
                new_segment_inputs,
                conversation.word_count,
                conversation.agent_ratio,
                conversation.customer_ratio,
            )
        )

        conversation.agent_ratio = agent_ratio
        conversation.customer_ratio = customer_ratio
        conversation.word_count = total_word_count

        # Calculate incremental duration and add to existing
        incremental_duration = calculate_duration_from_transcript(new_segment_inputs)
        conversation.duration = conversation.duration + incremental_duration

        # Get all messages for transcript JSON (if needed for tone analysis)
        all_messages = (
            await self.transcript_message_repo.get_messages_by_conversation_id(
                conversation_id,
            )
        )
        transcript_json = transcript_messages_to_json(
            all_messages, exclude_fields={"feedback", "type", "sequence_number"}
        )

        # Update conversation
        conversation.updated_by = get_current_user_id()
        conversation = await self.conversation_repo.update_conversation(conversation)

        # Perform partial tone check
        conversation = await self._analyze_in_progress_tone_and_mark(
            conversation,
            transcript_json,
            llm_analyst_id=in_progress_conv_update.llm_analyst_id,
        )

        full_conversation = await self.conversation_repo.fetch_conversation_by_id(
            conversation.id, include_messages=True
        )
        null_unloaded_attributes(full_conversation)
        return full_conversation

    async def save_new_messages(
        self,
        conversation_id: UUID,
        input_messages: list[TranscriptSegmentInput],
        next_sequence: int,
    ) -> list[TranscriptMessageModel]:
        """Save new messages and return them"""
        # Create new message models
        new_messages = [
            schema_to_transcript_message(segment, conversation_id, next_sequence + idx)
            for idx, segment in enumerate(input_messages)
        ]

        # Save new messages
        await self.transcript_message_repo.save_messages(new_messages)
        return new_messages

    def _validate_in_progress(self, conversation):
        if conversation.status == ConversationStatus.FINALIZED.value:
            raise AppException(ErrorKey.CONVERSATION_FINALIZED)
        if conversation.status == ConversationStatus.TAKE_OVER.value:
            raise AppException(ErrorKey.CONVERSATION_TAKEN_OVER)

    async def finalize_in_progress_conversation(
        self, llm_analyst_id: UUID, conversation_id: UUID
    ) -> ConversationAnalysisRead:
        """
        Finalize conversation and run GPT analysis
        """
        conversation = await self.conversation_repo.fetch_conversation_by_id(
            conversation_id
        )
        if not conversation:
            raise AppException(ErrorKey.CONVERSATION_NOT_FOUND)

        if conversation.status == ConversationStatus.FINALIZED.value:
            raise AppException(ErrorKey.CONVERSATION_FINALIZED)

        # Mark as finalized
        conversation.status = ConversationStatus.FINALIZED.value
        saved_conversation = await self.conversation_repo.update_conversation(
            conversation
        )

        # Get messages for analysis
        messages = await self.transcript_message_repo.get_messages_by_type(
            conversation_id, TranscriptMessageType.MESSAGE.value
        )

        # Convert to format needed for analysis

        message_type_segments = transcript_messages_to_json(
            messages, exclude_fields={"feedback", "type", "sequence_number"}
        )

        if message_type_segments == "[]":
            raise ValueError(f"No messages found for conversation {conversation_id}")

        # Run GPT analysis (rest remains the same)
        if not llm_analyst_id:
            from app.db.seed.seed_data_config import seed_test_data

            llm_analyst_id = seed_test_data.llm_analyst_kpi_analyzer_id

        llm_analyst = await self.llm_analyst_service.get_by_id(llm_analyst_id)

        gpt_analysis = await self.gpt_kpi_analyzer_service.analyze_transcript(
            message_type_segments, llm_analyst=llm_analyst
        )

        conversation_analysis = (
            await self.conversation_analysis_service.create_conversation_analysis(
                gpt_analysis, llm_analyst_id, saved_conversation.id
            )
        )

        # Update operator statistics
        await self.operator_statistics_service.update_from_analysis(
            conversation_analysis, conversation.operator_id, saved_conversation.duration
        )

        # Store in Zendesk if enabled
        store_in_zendesk = (
            os.getenv("STORE_CONVERSATIONS_IN_ZENDESK", "false").lower() == "true"
        )
        if store_in_zendesk:
            await self.store_zendesk_analysis(saved_conversation, conversation_analysis)

        return ConversationAnalysisRead.model_validate(conversation_analysis)

    async def store_zendesk_analysis(
        self,
        saved_conversation: ConversationModel,
        conversation_analysis: ConversationAnalysisModel,
    ):
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
                ticket_id=saved_conversation.zendesk_ticket_id, comment=comment_body
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
                tags=["genassist", "analyzed"],
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
    ) -> ConversationModel:

        #  Run GPT analysis
        if not llm_analyst_id:
            llm_analyst_id = seed_test_data.llm_analyst_kpi_analyzer_id

        llm_analyst = await self.llm_analyst_service.get_by_id(llm_analyst_id)
        analysis_result = (
            await self.gpt_kpi_analyzer_service.partial_hostility_analysis(
                transcript, llm_analyst=llm_analyst
            )
        )

        conversation.in_progress_hostility_score = analysis_result["hostile_score"]
        conversation.topic = analysis_result["topic"]
        conversation.negative_reason = analysis_result["negative_reason"]

        upd_conversation = await self.conversation_repo.update_conversation(
            conversation
        )
        return upd_conversation

    async def supervisor_takeover_conversation(self, conversation_id: UUID):
        conversation = await self.conversation_repo.fetch_conversation_by_id(
            conversation_id
        )
        self._validate_in_progress(conversation)
        segments = [
            TranscriptSegmentInput(
                create_time=datetime.now(),
                start_time=0,
                end_time=0,
                speaker="",
                text="",
                type="takeover",
            )
        ]
        transcript_update = InProgConvTranscrUpdate(messages=segments)

        # Get only the count for sequence numbering
        next_sequence = await self.transcript_message_repo.get_message_count(
            conversation_id
        )
        await self.save_new_messages(
            conversation_id, transcript_update.messages, next_sequence
        )
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

        models = await self.conversation_repo.fetch_conversations_with_relations(
            conversation_filter, include_messages=conversation_filter.include_messages
        )
        null_unloaded_attributes(models)
        return models

    async def count_conversations(self, conversation_filter: ConversationFilter) -> int:
        models = await self.conversation_repo.count_conversations(conversation_filter)
        return models

    async def get_stale_conversations(self, cutoff_time: datetime):
        models = await self.conversation_repo.get_stale_conversations(cutoff_time)
        return models

    async def delete_conversation(self, conversation_id: UUID):
        conversation = await self.conversation_repo.fetch_conversation_by_id(
            conversation_id
        )
        if not conversation:
            raise AppException(ErrorKey.CONVERSATION_NOT_FOUND)
        await self.conversation_repo.delete_conversation(conversation)
        return conversation

    async def cleanup_stale_conversations(self, cutoff_time: datetime):
        stale_conversations = await self.get_stale_conversations(cutoff_time)
        print(
            f"Got {len(stale_conversations)} stale conversations for cutoff time {cutoff_time}"
        )

        deleted_count = 0
        finalized_count = 0
        failed_count = 0

        # Process the stale conversations
        for conversation in stale_conversations:
            transcript = json.loads(conversation.transcription)
            if len(transcript) < 3:
                await self.delete_conversation(conversation.id)
                deleted_count += 1
                logger.info(
                    f"Deleted stale conversation {conversation.id} (last updated: {conversation.updated_at})"
                )
            else:
                try:
                    # Use the default KPI analyzer for finalization
                    await self.finalize_in_progress_conversation(
                        llm_analyst_id=seed_test_data.llm_analyst_kpi_analyzer_id,
                        conversation_id=conversation.id,
                    )
                    finalized_count += 1
                    logger.info(
                        f"Finalized conversation {conversation.id} (last updated: {conversation.updated_at})"
                    )
                except Exception as e:
                    logger.error(
                        f"Failed to finalize conversation {conversation.id}: {str(e)}"
                    )
                    failed_count += 1

        return {
            "deleted_count": deleted_count,
            "finalized_count": finalized_count,
            "failed_count": failed_count,
        }

    async def get_topics_count(self) -> Dict[str, int]:
        raw: List[Tuple[str, int]] = await self.conversation_repo.get_topics_count()

        topic_counts: Dict[str, int] = {}
        total_count = 0

        for topic, count in raw:
            normalized_topic = topic or "Other"
            topic_counts[normalized_topic] = count
            total_count += count

        return {"total": total_count, "details": topic_counts}

    async def add_conversation_feedback(
        self, conversation_id: UUID, feedback: Feedback, feedback_message: str
    ) -> ConversationModel:
        conversation = await self.conversation_repo.fetch_conversation_by_id(
            conversation_id
        )
        if not conversation:
            raise AppException(ErrorKey.CONVERSATION_NOT_FOUND, status_code=404)

        current_user_id = str(get_current_user_id())

        # Create feedback object
        feedback_object = {
            "feedback": feedback.value,
            "feedback_timestamp": datetime.now(timezone.utc).isoformat(),
            "feedback_user_id": current_user_id,
            "feedback_message": feedback_message,
        }

        # Get existing feedback array or create new one
        existing_feedback = (
            json.loads(conversation.feedback) if conversation.feedback else []
        )

        # Ensure it's a list (for backwards compatibility)
        if not isinstance(existing_feedback, list):
            existing_feedback = []

        # Check if user already has feedback in the array
        user_feedback_found = False
        for i, existing_feedback_item in enumerate(existing_feedback):
            if existing_feedback_item.get("feedback_user_id") == current_user_id:
                # Update existing feedback
                existing_feedback[i] = feedback_object
                user_feedback_found = True
                break

        # If user doesn't have existing feedback, add new one
        if not user_feedback_found:
            existing_feedback.append(feedback_object)

        conversation.feedback = json.dumps(existing_feedback)
        updated_conversation = await self.conversation_repo.update_conversation(
            conversation
        )
        return updated_conversation
