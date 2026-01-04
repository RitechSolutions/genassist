from uuid import UUID
from injector import inject
import os
import logging

from app.db.models.ml_model import MLModel
from app.repositories.ml_models import MLModelsRepository
from app.schemas.ml_model import MLModelCreate, MLModelUpdate
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException

logger = logging.getLogger(__name__)


@inject
class MLModelsService:
    """Service for ML models business logic."""

    def __init__(self, repository: MLModelsRepository):
        self.repository = repository

    async def create(self, ml_model: MLModelCreate) -> MLModel:
        """Create a new ML model."""
        # Check if a model with the same name already exists
        existing_model = await self.repository.get_by_name(ml_model.name)
        if existing_model:
            raise AppException(
                error_key=ErrorKey.ML_MODEL_NAME_EXISTS
            )

        db_ml_model = await self.repository.create(ml_model)
        return db_ml_model

    async def get_by_id(self, ml_model_id: UUID) -> MLModel:
        """Get ML model by ID."""
        db_ml_model = await self.repository.get_by_id(ml_model_id)
        return db_ml_model

    async def get_all(self):
        """Get all ML models."""
        db_ml_models = await self.repository.get_all()
        return db_ml_models

    async def update(self, ml_model_id: UUID, ml_model_update: MLModelUpdate) -> MLModel:
        """Update an existing ML model."""
        update_data = ml_model_update.model_dump(exclude_unset=True)

        # If name is being updated, check for uniqueness
        if 'name' in update_data:
            existing_model = await self.repository.get_by_name(update_data['name'])
            if existing_model and existing_model.id != ml_model_id:
                raise AppException(
                    error_key=ErrorKey.ML_MODEL_NAME_EXISTS
                )

        db_ml_model = await self.repository.update(ml_model_id, update_data)
        return db_ml_model

    async def delete(self, ml_model_id: UUID):
        """Delete an ML model and its associated .pkl file if it exists."""
        # Get the model first to access the pkl_file path
        ml_model = await self.repository.get_by_id(ml_model_id)

        # If there's a pkl_file, attempt to delete it
        if ml_model.pkl_file and os.path.exists(ml_model.pkl_file):
            try:
                os.remove(ml_model.pkl_file)
                logger.info(f"Deleted pkl file: {ml_model.pkl_file}")
            except OSError as e:
                logger.error(f"Error deleting pkl file {ml_model.pkl_file}: {str(e)}")
                # Continue with soft delete even if file deletion fails

        # Soft delete the model
        await self.repository.delete(ml_model_id)


