from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import Optional
from datetime import datetime
from enum import Enum


class ModelType(str, Enum):
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
    OTHER = "other"


class MLModelBase(BaseModel):
    name: Optional[str] = Field(None, max_length=255, description="Unique name for the ML model")
    description: Optional[str] = Field(None, description="Description of what the model does")
    model_type: Optional[ModelType] = Field(None, description="Type of machine learning model")
    pkl_file: Optional[str] = Field(None, max_length=500, description="Path to the uploaded .pkl file")
    pkl_file_id: Optional[str] = Field(None, max_length=500, description="File manager ID for the uploaded .pkl file")
    features: Optional[list[str]] = Field(None, description="List of feature names used by the model")
    target_variable: Optional[str] = Field(None, max_length=255, description="The prediction target variable")


class MLModelCreate(MLModelBase):
    name: str = Field(..., max_length=255, description="Unique name for the ML model")
    description: str = Field(..., description="Description of what the model does")
    model_type: ModelType = Field(..., description="Type of machine learning model")
    features: list[str] = Field(..., min_length=1, description="List of feature names (must not be empty)")
    target_variable: str = Field(..., max_length=255, description="The prediction target variable")

    @field_validator('features')
    @classmethod
    def validate_features_not_empty(cls, v):
        if not v or len(v) == 0:
            raise ValueError('Features list must not be empty')
        return v


class MLModelUpdate(MLModelBase):
    """Update schema - all fields are optional"""


class MLModelRead(MLModelBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
    )

