from uuid import UUID
from fastapi import APIRouter, Depends
from fastapi_injector import Injected

from app.auth.dependencies import auth, permissions
from app.auth.utils import generate_password
from app.schemas.operator import OperatorCreate, OperatorRead, OperatorReadAfterCreate
from app.services.operators import OperatorService


router = APIRouter()


@router.post("/", status_code=201, response_model=OperatorReadAfterCreate,
                      dependencies=[
                          Depends(auth),
                          Depends(permissions("update:operator"))
                          ])
async def create(operator: OperatorCreate, operator_service: OperatorService = Injected(OperatorService)):
    generated_password = generate_password()
    created_operator =  await operator_service.create(operator, generated_password=generated_password)
    operator_read_after_create = OperatorReadAfterCreate.model_validate(created_operator)
    operator_read_after_create.user.password = generated_password

    await operator_service.set_operator_latest_call(operator_read_after_create)
    return operator_read_after_create

@router.get("/", response_model=list[OperatorRead],
                     dependencies=[
                         Depends(auth),
                         Depends(permissions("read:operator"))
                         ])
async def get_all(operator_service: OperatorService = Injected(OperatorService)):
    operators =  await operator_service.get_all()
    enriched = []
    for operator in operators:
        # Add the latest call only if operator has more than 1 call to not duplicate data in frontend
        operator_read = OperatorRead.model_validate(operator)
        await operator_service.set_operator_latest_call(operator_read)

        enriched.append(operator)

    return enriched


@router.get("/{operator_id}", response_model=OperatorRead,
                     dependencies=[
                         Depends(auth),
                         Depends(permissions("read:operator"))
                         ])
async def get(operator_id: UUID, operator_service: OperatorService = Injected(OperatorService)):
    operator = operator_service.get_by_id(operator_id)
    operator_read = OperatorRead.model_validate(operator)
    await operator_service.set_operator_latest_call(operator_read)
