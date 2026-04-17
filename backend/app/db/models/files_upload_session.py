"""DB model for chunked uploads (file-manager-owned)."""

from typing import Optional

from sqlalchemy import BigInteger, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class FilesUploadSessionModel(Base):
    """
    Tracks a resumable/chunked upload before the file is registered in `files`
    and returned to the client in UploadFileResponse shape.
    """

    __tablename__ = "files_upload_sessions"
    __table_args__ = (Index("idx_files_upload_sessions_status", "status"),)

    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    content_type: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    temp_path: Mapped[str] = mapped_column(String(2000), nullable=False)
    bytes_received: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    expected_bytes: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    result_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

