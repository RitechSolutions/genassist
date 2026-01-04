from uuid import UUID
from injector import inject
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.exc import IntegrityError
from typing import List, Optional
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.db.models.ml_model import MLModel
from app.schemas.ml_model import MLModelCreate
from starlette_context import context
import logging

logger = logging.getLogger(__name__)


@inject
class MLModelsRepository:
    """Repository for ML model-related database operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, ml_model_data: MLModelCreate) -> MLModel:
        """Create a new ML model."""
        try:
            new_ml_model = MLModel(
                name=ml_model_data.name,
                description=ml_model_data.description,
                model_type=ml_model_data.model_type,
                pkl_file=ml_model_data.pkl_file,
                features=ml_model_data.features,
                target_variable=ml_model_data.target_variable,
                inference_params=ml_model_data.inference_params,
            )
            self.db.add(new_ml_model)
            await self.db.commit()
            await self.db.refresh(new_ml_model)
            return new_ml_model
        except IntegrityError as e:
            await self.db.rollback()
            logger.error(f"IntegrityError while creating ML model: {str(e)}")
            raise AppException(
                error_key=ErrorKey.ML_MODEL_NAME_EXISTS
            ) from e

    async def get_by_id(self, ml_model_id: UUID) -> MLModel:
        """Fetch ML model by ID."""
        query = select(MLModel).where(
            MLModel.id == ml_model_id,
            MLModel.is_deleted == 0
        )
        result = await self.db.execute(query)
        ml_model = result.scalars().first()

        if not ml_model:
            raise AppException(error_key=ErrorKey.ML_MODEL_NOT_FOUND)

        return ml_model

    async def get_by_name(self, name: str) -> Optional[MLModel]:
        """Fetch ML model by name."""
        query = select(MLModel).where(
            MLModel.name == name,
            MLModel.is_deleted == 0
        )
        result = await self.db.execute(query)
        return result.scalars().first()

    async def get_all(self) -> List[MLModel]:
        """Fetch all ML models."""
        query = (
            select(MLModel)
            .where(MLModel.is_deleted == 0)
            .order_by(MLModel.created_at.desc())
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def update(self, ml_model_id: UUID, update_data: dict) -> MLModel:
        """Update an existing ML model."""
        ml_model = await self.get_by_id(ml_model_id)

        try:
            for key, value in update_data.items():
                if hasattr(ml_model, key):
                    setattr(ml_model, key, value)

            # Update the updated_by field from context
            try:
                ml_model.updated_by = context.get("user_id")
            except LookupError:
                # Context not available, skip updating updated_by
                pass

            await self.db.commit()
            await self.db.refresh(ml_model)
            return ml_model
        except IntegrityError as e:
            await self.db.rollback()
            logger.error(f"IntegrityError while updating ML model: {str(e)}")
            raise AppException(
                error_key=ErrorKey.ML_MODEL_NAME_EXISTS
            ) from e

    async def delete(self, ml_model_id: UUID) -> MLModel:
        """Soft delete an ML model."""
        ml_model = await self.get_by_id(ml_model_id)
        ml_model.is_deleted = 1
        await self.db.commit()
        return ml_model


