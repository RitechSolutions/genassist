from typing import Optional
from sqlalchemy import String, Index, Text, BigInteger
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from enum import Enum
from app.db.base import Base

class StorageProvider(str, Enum):
    LOCAL = "local"
    S3 = "s3"
    AZURE = "azure"
    GCS = "gcs"
    SHAREPOINT = "sharepoint"
    DATABASE = "database"


class FileModel(Base):
    """
    SQLAlchemy model for a File.
    Stores file metadata including storage provider information.
    """

    __tablename__ = "files"
    __table_args__ = (
        Index("idx_files_path", "path"),
        Index("idx_files_storage_provider", "storage_provider"),
        Index("idx_files_storage_path", "storage_path"),
    )

    name: Mapped[str] = mapped_column(String(500), nullable=False)
    path: Mapped[str] = mapped_column(String(1000), nullable=False, index=True)
    size: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    mime_type: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    storage_provider: Mapped[str] = mapped_column(
        String(50), nullable=False, default=StorageProvider.LOCAL.value, index=True
    )
    storage_path: Mapped[str] = mapped_column(String(1000), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    file_extension: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    file_metadata: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    tags: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    permissions: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    def __repr__(self):
        return f"<FileModel(id='{self.id}', name='{self.name}', path='{self.path}', provider='{self.storage_provider}')>"
