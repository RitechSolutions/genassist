import logging
from injector import inject
from starlette_context import context
from uuid import UUID

from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.repositories.customers import CustomersRepository
from app.schemas.customer import CustomerCreate, CustomerUpdate


logger = logging.getLogger(__name__)


@inject
class CustomersService:
    def __init__(self, repository: CustomersRepository):
        self.repository = repository

    async def create(self, data: CustomerCreate):
        """
        Creates a new customer.
        """
        return await self.repository.create(data)

    async def get(self, customer_id: UUID):
        customer = await self.repository.get_by_id(customer_id)
        if not customer:
            raise AppException(error_key=ErrorKey.CUSTOMER_NOT_FOUND, status_code=404)
        return customer

    async def get_all(self, skip: int = 0, limit: int = 20):
        return await self.repository.get_all(skip, limit)

    async def delete(self, customer_id: UUID):
        customer = await self.repository.get_by_id(customer_id)
        if not customer:
            raise AppException(error_key=ErrorKey.CUSTOMER_NOT_FOUND, status_code=404)
        return await self.repository.soft_delete(customer)

    async def update(self, customer_id: UUID, data: CustomerUpdate):
        """
        Update an existing customer's fields.
        """
        model = await self.repository.update(context["user_id"], customer_id, data)
        return model