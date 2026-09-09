import enum
from typing import Optional

from sqlalchemy import Enum as SQLEnum
from sqlalchemy import Index, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ModelType(str, enum.Enum):
    XGBOOST = "xgboost"
    LIGHTGBM = "lightgbm"
    CATBOOST = "catboost"
    RANDOM_FOREST = "random_forest"
    EXTRA_TREES = "extra_trees"
    GRADIENT_BOOSTING = "gradient_boosting"
    DECISION_TREE = "decision_tree"
    LINEAR_REGRESSION = "linear_regression"
    RIDGE_REGRESSION = "ridge_regression"
    LASSO_REGRESSION = "lasso_regression"
    ELASTIC_NET = "elastic_net"
    LOGISTIC_REGRESSION = "logistic_regression"
    SVM = "svm"
    KNN = "knn"
    NEURAL_NETWORK = "neural_network"
    # Retained only so rows created before this type was retired still
    # deserialize (the Postgres enum type can't drop the value). New/updated
    # models are blocked from using it - see app.schemas.ml_model.
    OTHER = "other"


class MLModel(Base):
    __tablename__ = "ml_models"
    __table_args__ = (Index("idx_ml_models_name", "name", unique=True),)

    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    model_type: Mapped[ModelType] = mapped_column(
        SQLEnum(ModelType, name="model_type_enum", create_constraint=True), nullable=False
    )
    pkl_file: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    pkl_file_id: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    features: Mapped[list] = mapped_column(ARRAY(String), nullable=False)
    target_variable: Mapped[str] = mapped_column(String(255), nullable=False)
    inference_params: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Relationships
    pipeline_configs = relationship("MLModelPipelineConfig", back_populates="model", cascade="all, delete-orphan")
    pipeline_runs = relationship("MLModelPipelineRun", back_populates="model", cascade="all, delete-orphan")
