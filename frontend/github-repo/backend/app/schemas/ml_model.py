from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum


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
    features: Optional[list[str]] = Field(None, description="List of feature names used by the model")
    target_variable: Optional[str] = Field(None, max_length=255, description="The prediction target variable")
    inference_params: Optional[Dict[str, Any]] = Field(None, description="Key-value pairs for inference configuration")


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


class FileUploadResponse(BaseModel):
    file_path: str = Field(..., description="Path to the uploaded file")
    original_filename: str = Field(..., description="Original name of the uploaded file")


