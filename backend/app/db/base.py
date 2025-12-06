import uuid

from sqlalchemy.orm import DeclarativeBase
from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, Integer, text
from sqlalchemy import UUID, Column

from sqlalchemy.orm import Mapped, mapped_column

from app.auth.utils import get_current_user_id


class AuditMixin:
    created_by = Column(UUID(as_uuid=True), nullable=True,
                        default=get_current_user_id())
    updated_by = Column(UUID(as_uuid=True), nullable=True, default=None)


class TimestampMixin:
    created_at = Column(DateTime(timezone=True),
                        default=lambda: datetime.now(timezone.utc),
                        server_default=text('CURRENT_TIMESTAMP'))

    updated_at = Column(DateTime(timezone=True),
                        default=lambda: datetime.now(timezone.utc),
                        server_default=text('CURRENT_TIMESTAMP'),
                        onupdate=lambda: datetime.now(timezone.utc))


class SoftDeleteMixin:
    is_deleted: Mapped[Integer] = mapped_column(Integer, nullable=False, default=0,
                                                sort_order=10  # Always put as last column
                                                )


def generate_sequential_uuid():
    """
    Generates a UUID4 object that is intended to be sortable.
    If you're concerned about privacy, consider using a truly random UUID4.
    """
    try:
        import uuid6
        return uuid6.uuid7()  # This uses current timestamp, so it's somewhat sequential
    except ImportError:
        import time
        # Alternative that relies on current time (less precise/robust)
        return uuid.UUID(bytes=int(time.time() * 1000).to_bytes(8, 'big') + uuid.uuid4().bytes[8:])


class Base(DeclarativeBase, AuditMixin, TimestampMixin, SoftDeleteMixin):
    abstract = True
    id: Mapped[UUID] = mapped_column(
        UUID, primary_key=True, default=generate_sequential_uuid, sort_order=-1)

    def to_dict(self):
        result = {}
        for c in self.__table__.columns:
            value = getattr(self, c.name)
            # Convert UUID objects to strings
            if isinstance(value, uuid.UUID):
                value = str(value)
            result[c.name] = value
        return result
