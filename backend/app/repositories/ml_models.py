from uuid import UUID
from injector import inject
from sqlalchemy import func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.exc import IntegrityError
from typing import List, Optional, Sequence
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.db.models.ml_model import MLModel
from app.repositories.db_repository import DbRepository
from app.schemas.ml_model import MLModelCreate
from starlette_context import context
from starlette_context.errors import ContextDoesNotExistError
import logging

logger = logging.getLogger(__name__)


@inject
class MLModelsRepository(DbRepository[MLModel]):
    """Repository for ML model-related database operations."""

    def __init__(self, db: AsyncSession):
        super().__init__(MLModel, db)

    async def create(
        self, ml_model_data: MLModelCreate, training_metrics: Optional[dict] = None
    ) -> MLModel:
        """Create a new ML model."""
        try:
            new_ml_model = MLModel(
                name=ml_model_data.name,
                description=ml_model_data.description,
                model_type=ml_model_data.model_type,
                pkl_file=ml_model_data.pkl_file,
                pkl_file_id=ml_model_data.pkl_file_id,
                features=ml_model_data.features,
                target_variable=ml_model_data.target_variable,
                inference_params=ml_model_data.inference_params,
                training_metrics=training_metrics,
            )
            async with self.db.begin_nested():
                self.db.add(new_ml_model)
                await self.db.flush()
            await self.db.refresh(new_ml_model)
            return new_ml_model
        except IntegrityError as e:
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

    async def is_file_referenced(self, pkl_file_id: UUID, pkl_file_paths: Sequence[str] = ()) -> bool:
        """True when a live ML model points at this File Manager file, by id or by path.

        pkl_file_id is stored as free text, so the stored id is cleaned the way Python's
        UUID() reads it (no case, hyphens, braces, "urn:" or "uuid:" prefix): any spelling
        that still names this file counts.
        """
        stored_id = func.lower(MLModel.pkl_file_id)
        for noise in ("urn:", "uuid:", "-", "{", "}"):
            stored_id = func.replace(stored_id, noise, "")
        matches = [stored_id == pkl_file_id.hex]
        if pkl_file_paths:
            matches.append(MLModel.pkl_file.in_(list(pkl_file_paths)))
        query = select(MLModel.id).where(
            or_(*matches),
            MLModel.is_deleted == 0,
        ).limit(1)
        result = await self.db.execute(query)
        return result.first() is not None

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
            except (LookupError, ContextDoesNotExistError):
                # Context not available (e.g., in background tasks), skip updating updated_by
                pass

            async with self.db.begin_nested():
                await self.db.flush()
            await self.db.refresh(ml_model)
            return ml_model
        except IntegrityError as e:
            logger.error(f"IntegrityError while updating ML model: {str(e)}")
            raise AppException(
                error_key=ErrorKey.ML_MODEL_NAME_EXISTS
            ) from e

    async def delete(self, ml_model_id: UUID) -> MLModel:
        """Soft delete an ML model."""
        ml_model = await self.get_by_id(ml_model_id)
        ml_model.is_deleted = 1
        await self.db.flush()
        return ml_model

