"""Service for evaluating an existing ML model's .pkl file against a user-supplied CSV."""

import logging
import os
from typing import Any, Dict, Optional
from uuid import UUID

import pandas as pd
from injector import inject
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    precision_score,
    r2_score,
    recall_score,
)

from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.core.project_path import DATA_VOLUME
from app.modules.workflow.engine.nodes.ml.ml_model_inference_node import _build_input_array
from app.modules.workflow.engine.nodes.ml.ml_utils import is_classification_task
from app.schemas.ml_model import MLModelBase
from app.services.ml_model_manager import download_pkl_file, get_ml_model_manager
from app.services.ml_models import MLModelsService

logger = logging.getLogger(__name__)

ML_MODELS_UPLOAD_DIR = str(DATA_VOLUME / "ml_models")


@inject
class MLModelEvaluationService:
    """Runs an existing model's predict() over an uploaded CSV and scores the result."""

    def __init__(self, ml_models_service: MLModelsService):
        self.ml_models_service = ml_models_service

    async def evaluate_csv(
        self, model_id: UUID, df: pd.DataFrame, target_column: Optional[str] = None
    ) -> Dict[str, Any]:
        ml_model = await self.ml_models_service.get_by_id(model_id)
        if not ml_model:
            raise AppException(error_key=ErrorKey.ML_MODEL_NOT_FOUND)

        target_col = (target_column or ml_model.target_variable or "").strip()
        if not target_col:
            raise AppException(
                error_key=ErrorKey.MISSING_PARAMETER,
                error_detail="No target column specified and the model has no target_variable configured.",
            )
        if target_col not in df.columns:
            raise AppException(
                error_key=ErrorKey.INTERNAL_ERROR,
                error_detail=(
                    f"Target column '{target_col}' not found in the uploaded CSV. "
                    f"Available columns: {list(df.columns)}"
                ),
            )

        await self._ensure_pkl_file(ml_model)

        model_manager = get_ml_model_manager()
        try:
            model_response = await model_manager.get_model(
                model_id=model_id,
                pkl_file=ml_model.pkl_file,
                pkl_file_id=ml_model.pkl_file_id,
                updated_at=ml_model.updated_at,
            )
        except Exception as e:
            logger.error("Failed to load model %s: %s", model_id, e, exc_info=True)
            raise AppException(
                error_key=ErrorKey.INTERNAL_ERROR,
                error_detail=f"Could not load model: {e}. Ensure all dependencies are installed.",
            ) from e

        if "version" in model_response and model_response["version"] == "v2.0":
            model = model_response.get("model", {})
            metadata = model_response.get("metadata", {})
            feature_names = list(metadata.get("feature_columns") or ml_model.features or [])
        else:
            model = model_response.get("model", {})
            feature_names = list(getattr(model, "feature_names_in_", []) or ml_model.features or [])

        if not feature_names:
            feature_names = [c for c in df.columns if c != target_col]

        missing = [f for f in feature_names if f not in df.columns]
        if missing:
            raise AppException(
                error_key=ErrorKey.INTERNAL_ERROR,
                error_detail=f"The uploaded CSV is missing feature columns required by the model: {missing}",
            )

        if not hasattr(model, "predict"):
            raise AppException(
                error_key=ErrorKey.INTERNAL_ERROR, error_detail="Model does not have a predict method"
            )

        eval_df = df[df[target_col].notna()]
        if eval_df.empty:
            raise AppException(
                error_key=ErrorKey.INTERNAL_ERROR,
                error_detail="No rows with a non-empty target value were found in the uploaded CSV.",
            )

        y_true = eval_df[target_col]
        normalized_inputs = {feat: eval_df[feat].tolist() for feat in feature_names}
        input_data = _build_input_array(normalized_inputs, feature_names)

        try:
            y_pred = model.predict(input_data)
        except Exception as e:
            raise AppException(
                error_key=ErrorKey.INTERNAL_ERROR, error_detail=f"Model prediction failed: {e}"
            ) from e

        model_type_value = (
            ml_model.model_type.value if hasattr(ml_model.model_type, "value") else str(ml_model.model_type)
        )
        classification = is_classification_task(y_true, model_type_value)

        if classification:
            task_type = "classification"
            metrics = {
                "accuracy": float(accuracy_score(y_true, y_pred)),
                "precision": float(precision_score(y_true, y_pred, average="weighted", zero_division=0)),
                "recall": float(recall_score(y_true, y_pred, average="weighted", zero_division=0)),
                "f1_score": float(f1_score(y_true, y_pred, average="weighted", zero_division=0)),
            }
        else:
            task_type = "regression"
            mse = float(mean_squared_error(y_true, y_pred))
            metrics = {
                "mse": mse,
                "rmse": mse ** 0.5,
                "mae": float(mean_absolute_error(y_true, y_pred)),
                "r2_score": float(r2_score(y_true, y_pred)),
            }

        return {
            "task_type": task_type,
            "row_count": int(len(eval_df)),
            "target_column": target_col,
            "metrics": metrics,
        }

    async def _ensure_pkl_file(self, ml_model: Any) -> None:
        """Ensure the pkl file exists locally, downloading from file manager if needed."""
        if ml_model.pkl_file and os.path.exists(ml_model.pkl_file):
            return

        if ml_model.pkl_file_id:
            destination_path = os.path.join(ML_MODELS_UPLOAD_DIR, f"{ml_model.name}_{ml_model.id}.pkl")
            pkl_file_path = await download_pkl_file(ml_model.pkl_file_id, destination_path)
            await self.ml_models_service.update(ml_model.id, MLModelBase(pkl_file=str(pkl_file_path)))
            ml_model.pkl_file = str(pkl_file_path)
            return

        error_msg = f"PKL file not found for model {ml_model.name}"
        if ml_model.pkl_file:
            error_msg += f" at path: {ml_model.pkl_file}"
        raise AppException(error_key=ErrorKey.FILE_NOT_FOUND, error_detail=error_msg)