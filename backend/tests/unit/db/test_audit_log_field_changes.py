"""Unit tests for reading audit rows back in the shape the audit listener writes them"""

from datetime import date
from uuid import uuid4

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

import app.db.events  # noqa: F401  registers the listeners
import app.db.models  # noqa: F401  registers mappers for MessageIssueModel's relationship
import app.db.models.test_suite  # noqa: F401
from app.db.models.audit_log import AuditLogModel, field_changes
from app.db.models.message_issue import MessageIssueModel, MessageIssueNoteModel


def test_insert_update_and_delete_rows_read_back_as_field_changes():
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        MessageIssueModel.__table__.create(connection)
        AuditLogModel.__table__.create(connection)

    with Session(engine) as session:
        issue = MessageIssueModel(message_feedback_id=uuid4(), status="in_progress", fix_version="2.4.1")
        session.add(issue)
        session.flush()
        issue.status = "resolved"
        issue.target_rollout_date = date(2026, 10, 21)
        session.flush()
        session.delete(issue)
        session.flush()

        logs = {log.action_name: log for log in session.execute(select(AuditLogModel)).scalars()}

    inserted, updated, deleted = logs["Insert"], logs["Update"], logs["Delete"]
    assert field_changes(inserted)["status"] == (None, "in_progress")
    assert field_changes(inserted)["fix_version"] == (None, "2.4.1")
    assert field_changes(inserted)["target_rollout_date"] == (None, None)
    assert field_changes(updated)["status"] == ("in_progress", "resolved")
    assert field_changes(updated)["target_rollout_date"] == (None, "2026-10-21")
    assert field_changes(deleted) == {}


def test_note_body_is_redacted_in_insert_and_update_rows():
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        MessageIssueNoteModel.__table__.create(connection)
        AuditLogModel.__table__.create(connection)

    with Session(engine) as session:
        note = MessageIssueNoteModel(
            message_feedback_id=uuid4(),
            author_user_id=uuid4(),
            body="customer jane.roe@acme.com says the refund failed",
        )
        session.add(note)
        session.flush()
        note.body = "customer [EMAIL] says the refund failed"
        session.flush()

        logs = {log.action_name: log for log in session.execute(select(AuditLogModel)).scalars()}

    assert field_changes(logs["Insert"])["body"] == (None, "customer [EMAIL] says the refund failed")
    assert field_changes(logs["Update"])["body"] == (
        "customer [EMAIL] says the refund failed",
        "customer [EMAIL] says the refund failed",
    )
