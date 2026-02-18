import logging
from injector import inject
from sqlalchemy import UUID

from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.db.models.message_model import MessageFeedbackModel
from app.repositories.transcript_message import TranscriptMessageRepository
from app.schemas.conversation_transcript import (TranscriptSegmentFeedback)


logger = logging.getLogger(__name__)

@inject
class TranscriptMessageService:
    def __init__(self,
                 transcript_message_repository: TranscriptMessageRepository):
        self.transcript_message_repo = transcript_message_repository

    async def add_transcript_message_feedback(self, message_id: UUID, transcript_feedback:
    TranscriptSegmentFeedback)-> tuple[MessageFeedbackModel, UUID]:
        # Get message first to extract conversation_id
        message = await self.transcript_message_repo.get_message_by_message_id(message_id)
        if not message:
            raise AppException(ErrorKey.MESSAGE_NOT_FOUND)

        conversation_id = message.conversation_id

        # Add feedback (pass message to avoid re-querying)
        feedback = await self.transcript_message_repo.add_message_feedback(
            message_id, transcript_feedback
        )

        return feedback, conversation_id