from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, status
from fastapi_injector import Injected

from app.auth.dependencies import auth, permissions
from app.core.permissions.constants import Permissions as P
from app.schemas.test_suite import (
    TestEvaluation,
    TestEvaluationCreate,
    TestEvaluationUpdate,
)
from app.services.test_suite import TestSuiteService


router = APIRouter()


@router.get(
    "/evaluations",
    response_model=List[TestEvaluation],
    dependencies=[Depends(auth), Depends(permissions(P.Evaluation.READ))],
)
async def list_evaluations(
    service: TestSuiteService = Injected(TestSuiteService),
):
    return await service.list_evaluations()


@router.post(
    "/evaluations",
    response_model=TestEvaluation,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(auth), Depends(permissions(P.Evaluation.UPDATE))],
)
async def create_evaluation(
    data: TestEvaluationCreate,
    service: TestSuiteService = Injected(TestSuiteService),
):
    return await service.create_evaluation(data)


@router.get(
    "/evaluations/{evaluation_id}",
    response_model=TestEvaluation,
    dependencies=[Depends(auth), Depends(permissions(P.Evaluation.READ))],
)
async def get_evaluation(
    evaluation_id: UUID,
    service: TestSuiteService = Injected(TestSuiteService),
):
    return await service.get_evaluation(evaluation_id)


@router.patch(
    "/evaluations/{evaluation_id}",
    response_model=TestEvaluation,
    dependencies=[Depends(auth), Depends(permissions(P.Evaluation.UPDATE))],
)
async def update_evaluation(
    evaluation_id: UUID,
    data: TestEvaluationUpdate,
    service: TestSuiteService = Injected(TestSuiteService),
):
    return await service.update_evaluation(evaluation_id, data)


@router.post(
    "/evaluations/{evaluation_id}/runs/{run_id}",
    response_model=TestEvaluation,
    dependencies=[Depends(auth), Depends(permissions(P.Evaluation.UPDATE))],
)
async def append_run_to_evaluation(
    evaluation_id: UUID,
    run_id: UUID,
    service: TestSuiteService = Injected(TestSuiteService),
):
    return await service.append_run_to_evaluation(evaluation_id, str(run_id))


@router.delete(
    "/evaluations/{evaluation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(auth), Depends(permissions(P.Evaluation.UPDATE))],
)
async def delete_evaluation(
    evaluation_id: UUID,
    service: TestSuiteService = Injected(TestSuiteService),
):
    await service.delete_evaluation(evaluation_id)