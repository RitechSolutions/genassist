from typing import Optional
from sqlalchemy import String, Text, Index, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
import enum

from app.db.base import Base


class ModelType(str, enum.Enum):
    XGBOOST = "xgboost"
    RANDOM_FOREST = "random_forest"
    LINEAR_REGRESSION = "linear_regression"
    LOGISTIC_REGRESSION = "logistic_regression"
    OTHER = "other"


class MLModel(Base):
    __tablename__ = 'ml_models'
    __table_args__ = (
        Index('idx_ml_models_name', 'name', unique=True),
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    model_type: Mapped[ModelType] = mapped_column(
        SQLEnum(ModelType, name='model_type_enum', create_constraint=True),
        nullable=False
    )
    pkl_file: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    features: Mapped[list] = mapped_column(ARRAY(String), nullable=False)
    target_variable: Mapped[str] = mapped_column(String(255), nullable=False)
    inference_params: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Relationships
    pipeline_configs = relationship(
        "MLModelPipelineConfig",
        back_populates="model",
        cascade="all, delete-orphan"
    )
    pipeline_runs = relationship(
        "MLModelPipelineRun",
        back_populates="model",
        cascade="all, delete-orphan"
    )


