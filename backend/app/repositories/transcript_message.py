from typing import List, Optional
from uuid import UUID
from injector import inject
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.auth.utils import get_current_user_id
from app.db.models.message_model import MessageFeedbackModel, TranscriptMessageModel
from app.schemas.conversation_transcript import TranscriptSegmentFeedback


@inject
class TranscriptMessageRepository:
    def __init__(self, db: AsyncSession):
        self.db = db


    async def save_messages(self, messages: List[TranscriptMessageModel]) -> List[TranscriptMessageModel]:
        """Save multiple transcript messages"""
        self.db.add_all(messages)
        await self.db.commit()
        for msg in messages:
            await self.db.refresh(msg)
        return messages


    async def get_latest_sequence_number(
            self,
            conversation_id: UUID
            ) -> int:
        """Get the latest sequence number for a conversation (returns -1 if no messages)"""
        from sqlalchemy import func

        query = select(func.max(TranscriptMessageModel.sequence_number)).where(
                TranscriptMessageModel.conversation_id == conversation_id
                )
        result = await self.db.execute(query)
        max_seq = result.scalar()

        # Return -1 if no messages exist, so next_sequence will be 0
        return max_seq if max_seq is not None else -1


    async def get_messages_by_conversation_id(
            self,
            conversation_id: UUID,
            ) -> List[TranscriptMessageModel]:
        """Get all messages for a conversation, ordered by sequence"""
        query = select(TranscriptMessageModel).where(
                TranscriptMessageModel.conversation_id == conversation_id
                ).order_by(TranscriptMessageModel.sequence_number)

        query = query.options(selectinload(TranscriptMessageModel.feedback))

        result = await self.db.execute(query)
        return list(result.scalars().all())


    async def get_message_by_message_id(
            self,
            message_id: UUID,
            ) -> Optional[TranscriptMessageModel]:
        """Get a specific message by its message_id"""
        query = select(TranscriptMessageModel).where(
                TranscriptMessageModel.id == message_id
                )

        query = query.options(selectinload(TranscriptMessageModel.feedback))

        result = await self.db.execute(query)
        return result.scalars().first()


    async def add_message_feedback(
            self,
            message_id: UUID,
            transcript_feedback: TranscriptSegmentFeedback
            ) -> MessageFeedbackModel:
        """Add feedback to a message"""
        from datetime import datetime, timezone

        # Get the message
        message = await self.get_message_by_message_id(message_id)
        if not message:
            raise ValueError(f"Message with id {transcript_feedback.message_id} not found")

        # Check if user already has feedback
        existing_feedback = await self.get_user_feedback_for_message(
                message.id,
                get_current_user_id()
                )

        if existing_feedback:
            # Update existing feedback
            existing_feedback.feedback = transcript_feedback.feedback.value
            existing_feedback.feedback_timestamp = datetime.now(timezone.utc)
            existing_feedback.feedback_message = transcript_feedback.feedback_message
            await self.db.commit()
            await self.db.refresh(existing_feedback)
            return existing_feedback
        else:
            # Create new feedback
            new_feedback = MessageFeedbackModel(
                    message_id=message.id,
                    feedback=transcript_feedback.feedback.value,
                    feedback_timestamp=datetime.now(timezone.utc),
                    feedback_user_id=get_current_user_id(),
                    feedback_message=transcript_feedback.feedback_message
                    )
            self.db.add(new_feedback)
            await self.db.commit()
            await self.db.refresh(new_feedback)
            return new_feedback


    async def get_user_feedback_for_message(
            self,
            message_id: UUID,
            user_id: UUID
            ) -> Optional[MessageFeedbackModel]:
        """Get a specific user's feedback for a message"""
        query = select(MessageFeedbackModel).where(
                MessageFeedbackModel.message_id == message_id,
                MessageFeedbackModel.feedback_user_id == user_id
                )
        result = await self.db.execute(query)
        return result.scalars().first()


    async def delete_messages_by_conversation_id(self, conversation_id: UUID):
        """Delete all messages for a conversation (cascade will handle feedback)"""
        messages = await self.get_messages_by_conversation_id(conversation_id)
        for message in messages:
            await self.db.delete(message)
        await self.db.commit()


    async def get_messages_by_type(
            self,
            conversation_id: UUID,
            message_type: str
            ) -> List[TranscriptMessageModel]:
        """Get messages filtered by type"""
        query = select(TranscriptMessageModel).where(
                TranscriptMessageModel.conversation_id == conversation_id,
                TranscriptMessageModel.type == message_type
                ).order_by(TranscriptMessageModel.sequence_number)

        result = await self.db.execute(query)
        return list(result.scalars().all())


    async def get_message_count(self, conversation_id: UUID) -> int:
        """Get the count of messages for a conversation (for sequence numbering)"""
        query = select(func.count(TranscriptMessageModel.id)).where(
                TranscriptMessageModel.conversation_id == conversation_id
                )
        result = await self.db.execute(query)
        return result.scalar_one()