from uuid import UUID
from injector import inject
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.cache.redis_cache import make_key_builder
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.db.models.customer import CustomerModel
from app.schemas.customer import CustomerCreate, CustomerUpdate


customer_key_builder = make_key_builder("customer")


@inject
class CustomersRepository:
    """Repository for customer-related database operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, customer_create: CustomerCreate) -> CustomerModel:
        if customer_create.external_id:
            existing_customer = await self._get_by_external_id(customer_create.external_id)
            if existing_customer:
                raise AppException(ErrorKey.CUSTOMER_ALREADY_EXISTS, status_code=400)

        new_customer = CustomerModel(
            full_name=customer_create.full_name,
            phone=customer_create.phone,
            external_id=customer_create.external_id,
            is_active=customer_create.is_active,
            source_ref=customer_create.source_ref,
        )
        self.db.add(new_customer)
        await self.db.commit()
        await self.db.refresh(new_customer)
        return new_customer

    async def get_by_id(self, customer_id: UUID) -> CustomerModel:
        result = await self.db.execute(
            select(CustomerModel).where(CustomerModel.id == customer_id)
        )
        return result.scalars().first()

    async def _get_by_external_id(self, external_id: str) -> CustomerModel:
        result = await self.db.execute(
            select(CustomerModel).where(CustomerModel.external_id == external_id)
        )
        return result.scalars().first()

    async def get_all(self, skip: int = 0, limit: int = 20) -> list[CustomerModel]:
        query = (
            select(CustomerModel)
            .order_by(CustomerModel.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.db.execute(query)
        return result.scalars().all()

    async def update(self, customer_id: UUID, data: CustomerUpdate) -> CustomerModel:
        customer = await self.get_by_id(customer_id)
        if not customer:
            raise AppException(ErrorKey.CUSTOMER_NOT_FOUND, status_code=404)

        if data.full_name is not None:
            customer.full_name = data.full_name
        if data.phone is not None:
            customer.phone = data.phone
        if data.external_id is not None:
            customer.external_id = data.external_id
        if data.is_active is not None:
            customer.is_active = data.is_active
        if data.source_ref is not None:
            customer.source_ref = data.source_ref

        self.db.add(customer)
        await self.db.commit()
        await self.db.refresh(customer)
        return customer

    async def soft_delete(self, obj: CustomerModel) -> None:
        await self.db.execute(
            update(CustomerModel)
            .where(CustomerModel.id == obj.id)
            .values(is_deleted=True)
            .execution_options(synchronize_session="fetch")
        )
        await self.db.commit()