from typing import List, Optional
from uuid import UUID

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class TestEvaluationModel(Base):
    __tablename__ = "test_evaluations"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    suite_id: Mapped[UUID] = mapped_column(
        ForeignKey("test_suites.id"), nullable=False
    )
    workflow_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("workflows.id"), nullable=True
    )

    techniques: Mapped[List[str]] = mapped_column(JSONB, nullable=False, default=list)
    technique_configs: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    input_metadata: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Ordered list of run UUIDs (most recent first)
    run_ids: Mapped[List[str]] = mapped_column(JSONB, nullable=False, default=list)

    suite = relationship("TestSuiteModel")
    workflow = relationship("WorkflowModel")


class TestSuiteModel(Base):
    __tablename__ = "test_suites"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    workflow_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("workflows.id"), nullable=True
    )

    # Default metadata merged into each test case input_data before execution
    default_input_metadata: Mapped[Optional[dict]] = mapped_column(
        JSONB, nullable=True
    )

    # Relationships
    workflow = relationship("WorkflowModel", back_populates="test_suites")
    cases: Mapped[List["TestCaseModel"]] = relationship(
        "TestCaseModel",
        back_populates="suite",
        cascade="all, delete-orphan",
        lazy="noload",
    )
    runs: Mapped[List["TestRunModel"]] = relationship(
        "TestRunModel",
        back_populates="suite",
        cascade="all, delete-orphan",
        lazy="noload",
    )


class TestCaseModel(Base):
    __tablename__ = "test_cases"

    suite_id: Mapped[UUID] = mapped_column(
        ForeignKey("test_suites.id"), nullable=False
    )

    # Free-form scenario tags, e.g. ["refund", "es-ES"]
    tags: Mapped[Optional[List[str]]] = mapped_column(JSONB, nullable=True)

    # Input payload that will be merged with suite.default_input_metadata
    input_data: Mapped[dict] = mapped_column(JSONB, nullable=False)

    # Expected output (string or structured JSON) used by evaluators
    expected_output: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )

    weight: Mapped[Optional[float]] = mapped_column(nullable=True)

    suite = relationship("TestSuiteModel", back_populates="cases")
    results: Mapped[List["TestResultModel"]] = relationship(
        "TestResultModel",
        back_populates="case",
        cascade="all, delete-orphan",
        lazy="noload",
    )


class TestRunModel(Base):
    __tablename__ = "test_runs"

    suite_id: Mapped[UUID] = mapped_column(
        ForeignKey("test_suites.id"), nullable=False
    )
    workflow_id: Mapped[UUID] = mapped_column(
        ForeignKey("workflows.id"), nullable=False
    )

    # queued | running | completed | failed
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="queued",
    )

    # List of selected technique identifiers, e.g. ["exact_match", "nli_semantic_match"]
    techniques: Mapped[List[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
    )

    # Aggregated metrics for the run, keyed by technique
    summary_metrics: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    suite = relationship("TestSuiteModel", back_populates="runs")
    workflow = relationship("WorkflowModel")
    results: Mapped[List["TestResultModel"]] = relationship(
        "TestResultModel",
        back_populates="run",
        cascade="all, delete-orphan",
        lazy="noload",
    )


class TestResultModel(Base):
    __tablename__ = "test_results"

    run_id: Mapped[UUID] = mapped_column(
        ForeignKey("test_runs.id"), nullable=False
    )
    case_id: Mapped[UUID] = mapped_column(
        ForeignKey("test_cases.id"), nullable=False
    )

    # Truncated actual workflow output
    actual_output: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Optional full workflow execution trace / agent logs payload
    execution_trace: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )

    # Metrics per technique:
    # { technique_key: { "score": float|bool, "passed": bool, "comment": str|null } }
    metrics: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    run = relationship("TestRunModel", back_populates="results")
    case = relationship("TestCaseModel", back_populates="results")

