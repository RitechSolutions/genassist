from sqlalchemy import Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class IssueStatusModel(Base):
    __tablename__ = "issue_statuses"
    __table_args__ = (UniqueConstraint("key", name="uq_issue_statuses_key"),)

    key: Mapped[str] = mapped_column(String(50), nullable=False)
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    category: Mapped[str] = mapped_column(String(20), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    color: Mapped[str] = mapped_column(String(30), nullable=False)
    is_active: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
