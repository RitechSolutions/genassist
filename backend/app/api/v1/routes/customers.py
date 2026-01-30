from uuid import UUID
from fastapi import APIRouter, Depends
from fastapi_injector import Injected
from app.core.permissions.constants import Permissions as P
from app.auth.dependencies import auth, permissions
from app.schemas.customer import CustomerRead, CustomerCreate, CustomerUpdate
from app.services.customers import CustomersService

router = APIRouter()


@router.post("", response_model=CustomerRead, dependencies=[
    Depends(auth),
    Depends(permissions(P.Customer.CREATE))
])
async def create(customer: CustomerCreate, service: CustomersService = Injected(CustomersService)):
    """
    Create a customer.
    """
    return await service.create(customer)


@router.get("", response_model=list[CustomerRead], dependencies=[
    Depends(auth),
    Depends(permissions(P.Customer.READ))
])
async def get_all(skip: int = 0, limit: int = 20, service: CustomersService = Injected(CustomersService)):
    return await service.get_all(skip, limit)


@router.get("/{customer_id}", response_model=CustomerRead, dependencies=[
    Depends(auth),
    Depends(permissions(P.Customer.READ))
])
async def get(customer_id: UUID, service: CustomersService = Injected(CustomersService)):
    return await service.get(customer_id)


@router.delete("/{customer_id}", dependencies=[
    Depends(auth),
    Depends(permissions(P.Customer.DELETE))
])
async def delete(customer_id: UUID, service: CustomersService = Injected(CustomersService)):
    await service.delete(customer_id)
    return {"message": f"Customer with id: {customer_id} deleted successfully"}


@router.patch("/{customer_id}", response_model=CustomerRead, dependencies=[
    Depends(auth),
    Depends(permissions(P.Customer.UPDATE))
])
async def update(customer_id: UUID, customer_data: CustomerUpdate, service: CustomersService = Injected(CustomersService)):
    return await service.update(customer_id, customer_data)