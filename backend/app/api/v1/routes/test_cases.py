from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, status
from fastapi_injector import Injected

from app.auth.dependencies import auth, permissions
from app.core.permissions.constants import Permissions as P
from app.schemas.test_suite import (
    ImportCasesFromConversationRequest,
    TestCase,
    TestCaseCreate,
    TestCaseUpdate,
)
from app.services.test_suite import TestSuiteService


router = APIRouter()


@router.post(
    "/suites/{suite_id}/cases",
    response_model=TestCase,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(auth), Depends(permissions(P.Workflow.UPDATE))],
)
async def add_test_case(
    suite_id: UUID,
    data: TestCaseCreate,
    service: TestSuiteService = Injected(TestSuiteService),
):
    payload = data.model_copy(update={"suite_id": suite_id})
    return await service.add_case(payload)


@router.get(
    "/suites/{suite_id}/cases",
    response_model=List[TestCase],
    dependencies=[Depends(auth), Depends(permissions(P.Workflow.READ))],
)
async def list_test_cases(
    suite_id: UUID,
    service: TestSuiteService = Injected(TestSuiteService),
):
    return await service.list_cases_for_suite(suite_id)


@router.post(
    "/suites/{suite_id}/cases/import-from-conversation",
    response_model=List[TestCase],
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(auth), Depends(permissions(P.Workflow.UPDATE))],
)
async def import_cases_from_conversation(
    suite_id: UUID,
    data: ImportCasesFromConversationRequest,
    service: TestSuiteService = Injected(TestSuiteService),
):
    """
    Import all Q&A pairs from a conversation as test cases into the given suite.
    """
    return await service.import_cases_from_conversation(
        suite_id, data.conversation_id, data.replace
    )


@router.patch(
    "/cases/{case_id}",
    response_model=TestCase,
    dependencies=[Depends(auth), Depends(permissions(P.Workflow.UPDATE))],
)
async def update_test_case(
    case_id: UUID,
    data: TestCaseUpdate,
    service: TestSuiteService = Injected(TestSuiteService),
):
    return await service.update_case(case_id, data)


@router.delete(
    "/cases/{case_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(auth), Depends(permissions(P.Workflow.UPDATE))],
)
async def delete_test_case(
    case_id: UUID,
    service: TestSuiteService = Injected(TestSuiteService),
):
    await service.delete_case(case_id)