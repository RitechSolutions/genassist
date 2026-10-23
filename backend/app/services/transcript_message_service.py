import logging
from datetime import datetime, timezone
from typing import get_args
from injector import inject
from sqlalchemy import UUID

from app.auth.utils import get_current_user_id
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.core.utils.enums.issue_status_enum import DEFAULT_ISSUE_STATUS_KEY, IssueStatusCategory
from app.db.models.audit_log import field_changes
from app.db.models.message_model import MessageFeedbackModel
from app.repositories.issue_status import IssueStatusRepository
from app.repositories.transcript_message import TranscriptMessageRepository
from app.schemas.common import PaginatedResponse
from app.schemas.conversation_transcript import (TranscriptSegmentFeedback)
from app.schemas.filter import MessageIssueFilter, MessageIssueSummaryFilter
from app.schemas.message_issue import (
    IssueHistoryEvent,
    IssueHistoryField,
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
        rows, total = await self.transcript_message_repo.get_message_issues(filter_obj)
        items = [ReportedIssueRead.model_validate(row) for row in rows]
        return PaginatedResponse.from_filter(items, total, filter_obj)

    async def get_issue_status_summary(
        self, filter_obj: MessageIssueSummaryFilter
    ) -> IssueStatusSummary:
        """Reported issues counted per status, under the list's filters."""
        rows = await self.transcript_message_repo.count_message_issues_by_status(filter_obj)
        by_status = {s.key: 0 for s in await self.issue_status_repo.list_ordered()}
        by_status.update(dict(rows))
        return IssueStatusSummary(total=sum(by_status.values()), by_status=by_status)

    async def update_issue(
        self, message_feedback_id: UUID, update: IssueUpdate
    ) -> MessageIssueRead:
        changes = update.model_dump(exclude_unset=True)
        issue = await self.transcript_message_repo.get_or_add_issue(message_feedback_id)
        if "status" in changes and changes["status"] != issue.status:
            status = await self.issue_status_repo.get_by_key(changes["status"])
            if status is None or not status.is_active:
                raise AppException(ErrorKey.ISSUE_STATUS_NOT_FOUND, status_code=422)
            is_done = status.category == IssueStatusCategory.DONE.value
            changes["resolved_at"] = datetime.now(timezone.utc) if is_done else None
            changes["resolved_by"] = get_current_user_id() if is_done else None

        for key, value in changes.items():
            setattr(issue, key, value)
        return MessageIssueRead.model_validate(await self.transcript_message_repo.update(issue))

    async def list_issue_notes(self, message_feedback_id: UUID) -> list[IssueNoteRead]:
        rows = await self.transcript_message_repo.list_issue_notes(message_feedback_id)
        return [_note_read(note, username) for note, username in rows]

    async def add_issue_note(self, message_feedback_id: UUID, note: IssueNoteCreate) -> IssueNoteRead:
        created, username = await self.transcript_message_repo.add_issue_note(
            message_feedback_id, get_current_user_id(), note.body
        )
        return _note_read(created, username)

    async def list_issue_history(self, message_feedback_id: UUID) -> list[IssueHistoryEvent]:
        rows = await self.transcript_message_repo.list_issue_history(message_feedback_id)
        return [event for log, username in rows for event in _history_events(log, username)]


def _note_read(note, username) -> IssueNoteRead:
    return IssueNoteRead.model_validate(note).model_copy(update={"author_username": username})


_HISTORY_FIELDS = get_args(IssueHistoryField)
_NEW_ISSUE_VALUES = {"status": DEFAULT_ISSUE_STATUS_KEY}


def _history_events(log, username) -> list[IssueHistoryEvent]:
    changes = field_changes(log)

    def event(field, old=None, new=None):
        return IssueHistoryEvent(at=log.modified_at, by=username, field=field, old=old, new=new)

    if log.table_name == MessageFeedbackModel.__tablename__:
        old_comment, _ = changes.get("feedback_message", (None, None))
        return [event("comment")] if isinstance(old_comment, str) and old_comment.strip() else []
    if log.action_name == "Insert":
        changes = {field: (_NEW_ISSUE_VALUES.get(field), new) for field, (_, new) in changes.items()}
    pairs = [(field, *changes[field]) for field in _HISTORY_FIELDS if field in changes]
    return [event(field, old, new) for field, old, new in pairs if old != new]
