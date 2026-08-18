from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi_injector import Injected

from app.auth.dependencies import auth, permissions
from app.auth.utils import generate_password
from app.core.permissions.constants import Permissions as P
from app.schemas.common import PaginatedResponse
from app.schemas.filter import OperatorListFilter
from app.schemas.operator import OperatorCreate, OperatorListItem, OperatorRead, OperatorReadAfterCreate
from app.services.operators import OperatorService

router = APIRouter()


@router.post("", status_code=201, response_model=OperatorReadAfterCreate,
                      dependencies=[
                          Depends(auth),
                          Depends(permissions(P.Operator.UPDATE))
                          ])
async def create(operator: OperatorCreate, operator_service: OperatorService = Injected(OperatorService)):
    generated_password = generate_password()
    created_operator =  await operator_service.create(operator, generated_password=generated_password)
    operator_read_after_create = OperatorReadAfterCreate.model_validate(created_operator)
    operator_read_after_create.user.password = generated_password

    return operator_read_after_create

@router.get("", response_model=list[OperatorRead],
                     dependencies=[
                         Depends(auth),
                         Depends(permissions(P.Operator.READ))
                         ])
async def get_all(operator_service: OperatorService = Injected(OperatorService)):
    return await operator_service.get_all()


# Declared before /{operator_id} so "list" is not matched as a UUID path param.
@router.get("/list", response_model=PaginatedResponse[OperatorListItem],
                     dependencies=[
                         Depends(auth),
                         Depends(permissions(P.Operator.READ))
                         ])
async def get_list(filter_obj: OperatorListFilter = Depends(),
                   operator_service: OperatorService = Injected(OperatorService)):
    """Paginated operator list ordered by positive sentiment, then score"""
    return await operator_service.get_list_paginated(filter_obj)


@router.get("/{operator_id}", response_model=OperatorRead,
                     dependencies=[
                         Depends(auth),
                         Depends(permissions(P.Operator.READ))
                         ])
async def get(operator_id: UUID, operator_service: OperatorService = Injected(OperatorService)):
    return await operator_service.get_by_id(operator_id)
