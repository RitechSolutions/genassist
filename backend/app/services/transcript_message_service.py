import logging
from injector import inject
from sqlalchemy import UUID

from app.repositories.transcript_message import TranscriptMessageRepository
from app.schemas.conversation_transcript import (TranscriptSegmentFeedback)


logger = logging.getLogger(__name__)

@inject
class TranscriptMessageService:
    def __init__(self,
                 transcript_message_repository: TranscriptMessageRepository):
        self.transcript_message_repo = transcript_message_repository

    async def add_transcript_message_feedback(self, message_id: UUID, transcript_feedback: TranscriptSegmentFeedback):
        return await self.transcript_message_repo.add_message_feedback(message_id, transcript_feedback)