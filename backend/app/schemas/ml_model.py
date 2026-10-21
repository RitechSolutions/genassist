import os
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import Optional
from datetime import datetime
from enum import Enum

from app.core.project_path import DATA_VOLUME

# Local .pkl files of ML models must stay inside this folder.
ML_MODELS_DIR = str(DATA_VOLUME / "ml_models")


def is_in_ml_models_dir(path: str) -> bool:
    """True if path, with symlinks and '..' resolved, is a file path inside ML_MODELS_DIR."""
    root = os.path.realpath(ML_MODELS_DIR)
    resolved = os.path.realpath(path)
    return resolved != root and os.path.commonpath([root, resolved]) == root


class ModelType(str, Enum):
    XGBOOST = "xgboost"
    RANDOM_FOREST = "random_forest"
    LINEAR_REGRESSION = "linear_regression"
    LOGISTIC_REGRESSION = "logistic_regression"
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

    # Update is checked in MLModelsService.update instead, where the stored path is known:
    # the edit form sends an older model's stored pkl_file back unchanged.
    @field_validator('pkl_file')
    @classmethod
    def validate_pkl_file_in_ml_models_dir(cls, v):
        if v and not is_in_ml_models_dir(v):
            raise ValueError('pkl_file must be a file inside the ML models folder')
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

