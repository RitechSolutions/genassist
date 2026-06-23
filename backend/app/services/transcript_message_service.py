import logging
from injector import inject
from sqlalchemy import UUID

from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.core.utils.enums.issue_status_enum import IssueStatus
from app.db.models.message_issue import MessageIssueModel
from app.db.models.message_model import MessageFeedbackModel
from app.repositories.transcript_message import TranscriptMessageRepository
from app.schemas.common import PaginatedResponse
from app.schemas.conversation_transcript import (TranscriptSegmentFeedback)
from app.schemas.filter import MessageIssueFilter
from app.schemas.message_issue import ReportedIssueRead


logger = logging.getLogger(__name__)

@inject
class TranscriptMessageService:
    def __init__(self,
                 transcript_message_repository: TranscriptMessageRepository):
        self.transcript_message_repo = transcript_message_repository

    async def add_transcript_message_feedback(self, message_id: UUID, transcript_feedback:
    TranscriptSegmentFeedback)-> tuple[MessageFeedbackModel, UUID, str | None]:
        # Get message first to extract conversation_id
        message = await self.transcript_message_repo.get_message_by_message_id(message_id)
        if not message:
            raise AppException(ErrorKey.MESSAGE_NOT_FOUND)

        conversation_id = message.conversation_id

        # Add feedback (pass message to avoid re-querying)
        feedback, previous_feedback = await self.transcript_message_repo.add_message_feedback(
            message_id, transcript_feedback
        )

        return feedback, conversation_id, previous_feedback

    async def get_message_issues(
        self, filter_obj: MessageIssueFilter
    ) -> PaginatedResponse[ReportedIssueRead]:
        """Return a paginated list of commented messages (reported issues,
        newest first) with the context needed to act on them, for the review list."""
        rows, total = await self.transcript_message_repo.get_message_issues(
            skip=filter_obj.skip,
            limit=filter_obj.limit,
            status=filter_obj.status.value if filter_obj.status else None,
            from_date=filter_obj.from_date,
            to_date=filter_obj.to_date,
            workflow_id=filter_obj.workflow_id,
        )

        items = [
            ReportedIssueRead(
                feedback_id=feedback.id,
                message_id=message.id,
                conversation_id=conversation.id,
                agent_id=agent_id,
                workflow_name=workflow_name,
                text=message.text,
                speaker=message.speaker,
                comment=feedback.feedback_message,
                rating=feedback.feedback,
                status=issue_status,
                reported_by=username,
                reported_at=feedback.feedback_timestamp,
                conversation_topic=conversation.topic,
                conversation_date=conversation.conversation_date,
            )
            for (
                feedback,
                message,
                conversation,
                username,
                workflow_name,
                agent_id,
                issue_status,
            ) in rows
        ]
        return PaginatedResponse.from_filter(items, total, filter_obj)

    async def set_issue_status(
        self, message_feedback_id: UUID, status: IssueStatus
    ) -> MessageIssueModel:
        """Set the resolution status of a reported issue (a message comment)."""
        return await self.transcript_message_repo.set_issue_status(
            message_feedback_id, status.value
        )