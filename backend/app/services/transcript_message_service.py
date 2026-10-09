import logging
from datetime import datetime, timezone
from injector import inject
from sqlalchemy import UUID

from app.auth.utils import get_current_user_id
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.core.utils.enums.issue_status_enum import IssueStatusCategory
from app.db.models.message_model import MessageFeedbackModel
from app.repositories.issue_status import IssueStatusRepository
from app.repositories.transcript_message import TranscriptMessageRepository
from app.schemas.common import PaginatedResponse
from app.schemas.conversation_transcript import (TranscriptSegmentFeedback)
from app.schemas.filter import MessageIssueFilter, MessageIssueSummaryFilter
from app.schemas.message_issue import (
    IssueNoteCreate,
    IssueNoteRead,
    IssueStatusSummary,
    IssueUpdate,
    MessageIssueRead,
    ReportedIssueRead,
)


logger = logging.getLogger(__name__)

@inject
class TranscriptMessageService:
    def __init__(self,
                 transcript_message_repository: TranscriptMessageRepository,
                 issue_status_repository: IssueStatusRepository):
        self.transcript_message_repo = transcript_message_repository
        self.issue_status_repo = issue_status_repository

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
            status=filter_obj.status,
            from_date=filter_obj.from_date,
            to_date=filter_obj.to_date,
            workflow_id=filter_obj.workflow_id,
            topic=filter_obj.topic,
            subtopic=filter_obj.subtopic,
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
                conversation_topic=topic,
                conversation_subtopic=subtopic,
                conversation_date=conversation.conversation_date,
                fix_version=issue.fix_version if issue else None,
                target_rollout_date=issue.target_rollout_date if issue else None,
            )
            for (
                feedback,
                message,
                conversation,
                username,
                workflow_name,
                agent_id,
                issue_status,
                issue,
                topic,
                subtopic,
            ) in rows
        ]
        return PaginatedResponse.from_filter(items, total, filter_obj)

    async def get_issue_status_summary(
        self, filter_obj: MessageIssueSummaryFilter
    ) -> IssueStatusSummary:
        """Reported issues counted per status, under the list's filters."""
        rows = await self.transcript_message_repo.count_message_issues_by_status(
            from_date=filter_obj.from_date,
            to_date=filter_obj.to_date,
            workflow_id=filter_obj.workflow_id,
            topic=filter_obj.topic,
            subtopic=filter_obj.subtopic,
        )
        by_status = {s.key: 0 for s in await self.issue_status_repo.list_ordered()}
        by_status.update(dict(rows))
        return IssueStatusSummary(total=sum(by_status.values()), by_status=by_status)

    async def update_issue(
        self, message_feedback_id: UUID, update: IssueUpdate
    ) -> MessageIssueRead:
        changes = update.model_dump(exclude_unset=True)
        if "status" in changes:
            status = await self.issue_status_repo.get_by_key(changes["status"])
            if status is None or not status.is_active:
                raise AppException(ErrorKey.ISSUE_STATUS_NOT_FOUND, status_code=422)
            is_done = status.category == IssueStatusCategory.DONE.value
            changes["resolved_at"] = datetime.now(timezone.utc) if is_done else None
            changes["resolved_by"] = get_current_user_id() if is_done else None

        issue = await self.transcript_message_repo.upsert_issue(
            message_feedback_id, changes
        )
        return MessageIssueRead.model_validate(issue)

    async def set_issue_status(
        self, message_feedback_id: UUID, status: str
    ) -> MessageIssueRead:
        """Set the resolution status of a reported issue (a message comment)."""
        return await self.update_issue(message_feedback_id, IssueUpdate(status=status))

    async def list_issue_notes(self, message_feedback_id: UUID) -> list[IssueNoteRead]:
        rows = await self.transcript_message_repo.list_issue_notes(message_feedback_id)
        return [_note_read(note, username) for note, username in rows]

    async def add_issue_note(self, message_feedback_id: UUID, note: IssueNoteCreate) -> IssueNoteRead:
        created, username = await self.transcript_message_repo.add_issue_note(
            message_feedback_id, get_current_user_id(), note.body
        )
        return _note_read(created, username)


def _note_read(note, username) -> IssueNoteRead:
    return IssueNoteRead.model_validate(note).model_copy(update={"author_username": username})
