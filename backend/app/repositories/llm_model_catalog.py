import logging
from uuid import UUID

from injector import inject
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.db.models.llm import LlmProvidersModel
from app.db.models.llm_model_catalog import LlmModelCatalogModel
from app.repositories.db_repository import DbRepository

logger = logging.getLogger(__name__)


@inject
class LlmModelCatalogRepository(DbRepository[LlmModelCatalogModel]):
    def __init__(self, db: AsyncSession):
        super().__init__(LlmModelCatalogModel, db)

    async def create(self, obj: LlmModelCatalogModel) -> LlmModelCatalogModel:
        try:
            return await super().create(obj)
        except IntegrityError as e:
            await self.db.rollback()
            logger.warning("Duplicate active LLM catalog model rejected by the database: %s", e)
            raise AppException(error_key=ErrorKey.LLM_CATALOG_MODEL_ALREADY_EXISTS, status_code=409) from e

    async def list_all(self) -> list[LlmModelCatalogModel]:
        """Every catalog row, active or not — the management screen shows both."""
        result = await self.db.execute(
            select(LlmModelCatalogModel)
            .where(LlmModelCatalogModel.is_deleted == 0)
            .order_by(
                LlmModelCatalogModel.provider_key,
                LlmModelCatalogModel.label,
            )
        )
        return list(result.scalars().all())

    async def list_active(self) -> list[LlmModelCatalogModel]:
        """Rows that should appear in the provider form's Model dropdown."""
        result = await self.db.execute(
            select(LlmModelCatalogModel)
            .where(
                LlmModelCatalogModel.is_deleted == 0,
                LlmModelCatalogModel.is_active == 1,
            )
            .order_by(
                LlmModelCatalogModel.provider_key,
                LlmModelCatalogModel.label,
            )
        )
        return list(result.scalars().all())

    async def get_active_by_id(self, entry_id: UUID) -> LlmModelCatalogModel | None:
        result = await self.db.execute(
            select(LlmModelCatalogModel).where(
                LlmModelCatalogModel.id == entry_id,
                LlmModelCatalogModel.is_deleted == 0,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_provider_model(
        self, provider_key: str, model_key: str
    ) -> LlmModelCatalogModel | None:
        provider_key = (provider_key or "").strip().lower()
        model_key = (model_key or "").strip()
        result = await self.db.execute(
            select(LlmModelCatalogModel).where(
                func.lower(func.trim(LlmModelCatalogModel.provider_key)) == provider_key,
                func.trim(LlmModelCatalogModel.model_key) == model_key,
                LlmModelCatalogModel.is_deleted == 0,
            )
        )
        return result.scalar_one_or_none()

    async def soft_delete_by_id(self, entry_id: UUID) -> bool:
        row = await self.get_active_by_id(entry_id)
        if not row:
            return False
        row.is_deleted = 1
        await self.db.commit()
        return True

    async def list_models_in_use(self) -> list[tuple[str, str]]:
        """``(provider_type, model)`` pairs already saved on configured providers.

        Used to guarantee a provider's own model always stays selectable in the
        edit form, even if that model later leaves the built-in list.
        """
        result = await self.db.execute(
            select(
                LlmProvidersModel.llm_model_provider,
                LlmProvidersModel.llm_model,
            )
            .where(
                LlmProvidersModel.is_deleted == 0,
                LlmProvidersModel.llm_model_provider.isnot(None),
                LlmProvidersModel.llm_model.isnot(None),
            )
            .distinct()
        )
        return [(row[0], row[1]) for row in result.all() if row[0] and row[1]]
