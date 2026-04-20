from typing import Optional
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class PromptVersionModel(Base):
    __tablename__ = "prompt_versions"

    workflow_id: Mapped[UUID] = mapped_column(
        ForeignKey("workflows.id"), nullable=False
    )
    node_id: Mapped[str] = mapped_column(String(100), nullable=False)
    prompt_field: Mapped[str] = mapped_column(String(50), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    label: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    workflow = relationship("WorkflowModel")

    __table_args__ = (
        UniqueConstraint(
            "workflow_id",
            "node_id",
            "prompt_field",
            "version_number",
            name="uq_prompt_version_context",
        ),
    )


class PromptConfigModel(Base):
    __tablename__ = "prompt_configs"

    workflow_id: Mapped[UUID] = mapped_column(
        ForeignKey("workflows.id"), nullable=False
    )
    node_id: Mapped[str] = mapped_column(String(100), nullable=False)
    prompt_field: Mapped[str] = mapped_column(String(50), nullable=False)
    gold_suite_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("test_suites.id"), nullable=True
    )

    workflow = relationship("WorkflowModel")
    gold_suite = relationship("TestSuiteModel")

    __table_args__ = (
        UniqueConstraint(
            "workflow_id",
            "node_id",
            "prompt_field",
            name="uq_prompt_config_context",
        ),
    )
