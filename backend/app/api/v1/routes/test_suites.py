from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, status
from fastapi_injector import Injected

from app.auth.dependencies import auth, permissions
from app.core.permissions.constants import Permissions as P
from app.schemas.test_suite import (
    TestSuite,
    TestSuiteCreate,
    TestSuiteUpdate,
)
from app.services.test_suite import TestSuiteService


router = APIRouter()


@router.get(
    "/suites",
    response_model=List[TestSuite],
    dependencies=[Depends(auth), Depends(permissions(P.Evaluation.READ))],
)
async def list_test_suites(
    service: TestSuiteService = Injected(TestSuiteService),
):
    return await service.list_suites()


@router.post(
    "/suites",
    response_model=TestSuite,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(auth), Depends(permissions(P.Evaluation.UPDATE))],
)
async def create_test_suite(
    data: TestSuiteCreate,
    service: TestSuiteService = Injected(TestSuiteService),
):
    return await service.create_suite(data)


@router.get(
    "/suites/{suite_id}",
    response_model=TestSuite,
    dependencies=[Depends(auth), Depends(permissions(P.Evaluation.READ))],
)
async def get_test_suite(
    suite_id: UUID,
    service: TestSuiteService = Injected(TestSuiteService),
):
    return await service.get_suite(suite_id)


@router.patch(
    "/suites/{suite_id}",
    response_model=TestSuite,
    dependencies=[Depends(auth), Depends(permissions(P.Evaluation.UPDATE))],
)
async def update_test_suite(
    suite_id: UUID,
    data: TestSuiteUpdate,
    service: TestSuiteService = Injected(TestSuiteService),
):
    return await service.update_suite(suite_id, data)


@router.delete(
    "/suites/{suite_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(auth), Depends(permissions(P.Evaluation.UPDATE))],
)
async def delete_test_suite(
    suite_id: UUID,
    service: TestSuiteService = Injected(TestSuiteService),
):
    await service.delete_suite(suite_id)