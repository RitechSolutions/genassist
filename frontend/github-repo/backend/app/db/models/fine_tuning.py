from sqlalchemy import (
    Column,
    String,
    Integer,
    DateTime,
    ForeignKey,
    Enum,
    Text,
    Numeric,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.core.utils.enums.open_ai_fine_tuning_enum import FileStatus, JobStatus
from app.db.base import Base


class OpenAIFileModel(Base):
    __tablename__ = "openai_files"

    openai_file_id = Column(String, unique=True, nullable=False, index=True)
    filename = Column(String, nullable=False)
    purpose = Column(String, nullable=False)
    bytes = Column(Integer, nullable=False)
    status = Column(Enum(FileStatus), default=FileStatus.UPLOADED, nullable=False)

    # Relationships
    training_jobs = relationship(
        "FineTuningJobModel",
        back_populates="training_file",
        foreign_keys="FineTuningJobModel.training_file_id",
    )
    validation_jobs = relationship(
        "FineTuningJobModel",
        back_populates="validation_file",
        foreign_keys="FineTuningJobModel.validation_file_id",
    )


class FineTuningJobModel(Base):
    __tablename__ = "fine_tuning_jobs"

    openai_job_id = Column(String, unique=True, nullable=False, index=True)

    # File references
    training_file_id = Column(
        UUID(as_uuid=True), ForeignKey("openai_files.id"), nullable=False
    )
    validation_file_id = Column(
        UUID(as_uuid=True), ForeignKey("openai_files.id"), nullable=True
    )

    # Job configuration
    model = Column(String, nullable=False)
    hyperparameters = Column(JSONB, nullable=True)
    suffix = Column(String(40), nullable=True)

    # Job status
    status = Column(
        Enum(JobStatus), default=JobStatus.QUEUED, nullable=False, index=True
    )
    fine_tuned_model = Column(String, nullable=True)

    # Timestamps
    finished_at = Column(DateTime(timezone=True), nullable=True)
    last_synced_at = Column(DateTime(timezone=True), nullable=True)

    # Metrics
    trained_tokens = Column(Integer, nullable=True)
    cost_estimate = Column(Numeric(10, 4), nullable=True)

    # Error handling
    error_message = Column(Text, nullable=True)
    error_code = Column(String, nullable=True)

    # Relationships
    training_file = relationship(
        "OpenAIFileModel",
        back_populates="training_jobs",
        foreign_keys=[training_file_id],
    )
    validation_file = relationship(
        "OpenAIFileModel",
        back_populates="validation_jobs",
        foreign_keys=[validation_file_id],
    )

    events = relationship(
        "FineTuningEventModel",
        back_populates="job",
        cascade="all, delete-orphan",
        order_by="FineTuningEventModel.event_created_at"
    )


class FineTuningEventModel(Base):
    __tablename__ = "fine_tuning_events"

    # Foreign key to job
    job_id = Column(
            UUID(as_uuid=True),
            ForeignKey("fine_tuning_jobs.id"),
            nullable=False,
            index=True
            )

    # OpenAI event data
    openai_event_id = Column(String, unique=True, nullable=False, index=True)
    level = Column(String, nullable=False)  # 'info', 'warning', 'error'
    message = Column(Text, nullable=False)
    event_created_at = Column(DateTime(timezone=True), nullable=False)  # OpenAI's timestamp

    # Metrics stored as JSONB (step, train_loss, train_accuracy, etc.)
    metrics = Column(JSONB, nullable=True)

    # Relationship
    job = relationship("FineTuningJobModel", back_populates="events")
