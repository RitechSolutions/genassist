"""Unit tests for tracking whether a session's transaction has written anything"""

from uuid import uuid4

import pytest
from sqlalchemy import Column, String, Uuid, create_engine, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Session
from sqlalchemy.pool import StaticPool

import app.db.events  # noqa: F401  registers the listeners
from app.core.utils.db_connection_utils import release_idle_connection
from app.db.events.write_tracking import session_has_writes
from app.db.models.audit_log import AuditLogModel


class _Base(DeclarativeBase):
    pass


class Note(_Base):
    __tablename__ = "notes"
    id = Column(Uuid, primary_key=True, default=uuid4)
    text = Column(String)


def _create_tables(connection):
    _Base.metadata.create_all(connection)
    # The global audit listener records every insert, so its table must exist too.
    AuditLogModel.__table__.create(connection)


@pytest.fixture
def session():
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        _create_tables(connection)
    with Session(engine) as session:
        session.add(Note(text="seed"))
        session.commit()
        yield session


def test_reads_do_not_count_as_writes(session):
    session.execute(select(Note)).all()

    assert session.in_transaction()
    assert session_has_writes(session) is False


def test_pending_and_flushed_changes_count_until_the_transaction_ends(session):
    session.add(Note(text="new"))
    assert session_has_writes(session) is True

    session.flush()
    assert session_has_writes(session) is True

    session.commit()
    assert session_has_writes(session) is False


def test_statement_writes_count_until_rollback(session):
    session.execute(update(Note).values(text="changed"))
    assert session_has_writes(session) is True

    session.rollback()
    assert session_has_writes(session) is False


def test_raw_sql_and_locking_selects_count_as_writes(session):
    session.execute(text("SELECT 1")).all()
    assert session_has_writes(session) is True
    session.rollback()

    session.execute(select(Note).with_for_update()).all()
    assert session_has_writes(session) is True


@pytest.mark.asyncio
async def test_async_session_is_tracked_and_released_only_when_read_only():
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    async with engine.begin() as connection:
        await connection.run_sync(_create_tables)

    async with AsyncSession(engine, expire_on_commit=False) as session:
        (await session.execute(select(Note))).all()
        assert session.in_transaction() is True
        assert session_has_writes(session) is False

        assert await release_idle_connection(session=session) is True
        assert session.in_transaction() is False

        session.add(Note(text="new"))
        await session.flush()
        assert session_has_writes(session) is True

        assert await release_idle_connection(session=session) is False
        assert session.in_transaction() is True

    await engine.dispose()
