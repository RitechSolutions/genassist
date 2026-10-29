import os
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import Optional
from datetime import datetime
from enum import Enum
from math import isfinite


FEATURE_DEFAULTS_PARAM = "featureDefaults"

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


class MLModelBase(BaseModel):
    name: Optional[str] = Field(None, max_length=255, description="Unique name for the ML model")
    description: Optional[str] = Field(None, description="Description of what the model does")
    model_type: Optional[ModelType] = Field(None, description="Type of machine learning model")
    pkl_file: Optional[str] = Field(None, max_length=500, description="Path to the uploaded .pkl file")
    pkl_file_id: Optional[str] = Field(None, max_length=500, description="File manager ID for the uploaded .pkl file")
    features: Optional[list[str]] = Field(None, description="List of feature names used by the model")
    target_variable: Optional[str] = Field(None, max_length=255, description="The prediction target variable")
    inference_params: Optional[dict] = Field(
        None,
        description=(
            "Per-model inference configuration. `ratioBaselineColumn` identifies an extra "
            "caller input needed to reconstruct ratio-target predictions. `featureDefaults` "
            "maps model feature names to deliberate fallback values for omitted or null inputs."
        ),
    )


class MLModelWriteBase(MLModelBase):
    @field_validator("inference_params")
    @classmethod
    def validate_inference_params(cls, value):
        if value is None:
            return value

        feature_defaults = value.get(FEATURE_DEFAULTS_PARAM)
        if feature_defaults is not None:
            if not isinstance(feature_defaults, dict):
                raise ValueError(f"{FEATURE_DEFAULTS_PARAM} must be an object")
            invalid_defaults = [
                name
                for name, default in feature_defaults.items()
                if not isinstance(name, str)
                or not name.strip()
                or isinstance(default, (dict, list))
                or default is None
                or (isinstance(default, float) and not isfinite(default))
            ]
            if invalid_defaults:
                raise ValueError(
                    f"{FEATURE_DEFAULTS_PARAM} values must be non-null JSON scalars for: "
                    + ", ".join(str(name) for name in invalid_defaults)
                )

        ratio_baseline = value.get("ratioBaselineColumn")
        if ratio_baseline is not None and (
            not isinstance(ratio_baseline, str) or not ratio_baseline.strip()
        ):
            raise ValueError("ratioBaselineColumn must be a non-empty string")

        return value


class MLModelCreate(MLModelWriteBase):
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


class MLModelUpdate(MLModelWriteBase):
    """Update schema - all fields are optional"""


class MLModelRead(MLModelBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
    )
