from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, status
from fastapi_injector import Injected

from app.auth.dependencies import auth, permissions
from app.core.permissions.constants import Permissions as P
from app.schemas.test_suite import (
    AddConversationToSuitesRequest,
    AddConversationToSuitesResult,
    ConversationSuiteMembership,
    ImportCasesFromConversationRequest,
    ImportCasesFromConversationsRequest,
    ImportCasesFromConversationsResult,
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


@router.post(
    "/suites/{suite_id}/cases/import-from-conversations",
    response_model=ImportCasesFromConversationsResult,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(auth), Depends(permissions(P.Workflow.UPDATE))],
)
async def import_cases_from_conversations(
    suite_id: UUID,
    data: ImportCasesFromConversationsRequest,
    service: TestSuiteService = Injected(TestSuiteService),
):
    """
    Import the Q&A pairs of several conversations into the given suite at once.

    A conversation that cannot be imported is reported in ``results`` rather than
    failing the request, so one bad pick does not discard the rest of the batch.
    """
    return await service.import_cases_from_conversations(
        suite_id, data.conversation_ids, data.replace
    )


@router.get(
    "/conversations/{conversation_id}/suites",
    response_model=List[ConversationSuiteMembership],
    dependencies=[Depends(auth), Depends(permissions(P.Evaluation.READ))],
)
async def list_suites_for_conversation(
    conversation_id: UUID,
    service: TestSuiteService = Injected(TestSuiteService),
):
    """
    List every dataset, with how much of this conversation each already holds.

    Gated like ``GET /suites``, which it is a per-conversation view of.
    """
    return await service.list_suites_for_conversation(conversation_id)


@router.post(
    "/conversations/{conversation_id}/suites",
    response_model=AddConversationToSuitesResult,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(auth), Depends(permissions(P.Workflow.UPDATE))],
)
async def add_conversation_to_suites(
    conversation_id: UUID,
    data: AddConversationToSuitesRequest,
    service: TestSuiteService = Injected(TestSuiteService),
):
    """
    Add one conversation's Q&A pairs to several datasets at once.

    A dataset that already holds the conversation has its turns refreshed. A
    dataset that cannot be written is reported in ``results`` rather than failing
    the request, so one bad pick does not discard the rest.
    """
    return await service.add_conversation_to_suites(conversation_id, data.suite_ids)


@router.delete(
    "/suites/{suite_id}/conversations/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(auth), Depends(permissions(P.Workflow.UPDATE))],
)
async def remove_conversation_from_suite(
    suite_id: UUID,
    conversation_id: UUID,
    service: TestSuiteService = Injected(TestSuiteService),
):
    """Remove every case imported from one conversation, leaving the rest intact."""
    await service.remove_conversation_from_suite(suite_id, conversation_id)


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