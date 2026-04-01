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
    TestEvaluation,
    TestEvaluationCreate,
    TestEvaluationUpdate,
    TestResult,
    TestRun,
    TestRunCreate,
    TestSuite,
    TestSuiteCreate,
    TestSuiteUpdate,
)
from app.services.test_suite import TestSuiteService


router = APIRouter()


@router.get(
    "/suites",
    response_model=List[TestSuite],
    dependencies=[Depends(auth), Depends(permissions(P.Workflow.READ))],
)
async def list_test_suites(
    service: TestSuiteService = Injected(TestSuiteService),
):
    return await service.list_suites()


@router.post(
    "/suites",
    response_model=TestSuite,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(auth), Depends(permissions(P.Workflow.UPDATE))],
)
async def create_test_suite(
    data: TestSuiteCreate,
    service: TestSuiteService = Injected(TestSuiteService),
):
    return await service.create_suite(data)


@router.get(
    "/suites/{suite_id}",
    response_model=TestSuite,
    dependencies=[Depends(auth), Depends(permissions(P.Workflow.READ))],
)
async def get_test_suite(
    suite_id: UUID,
    service: TestSuiteService = Injected(TestSuiteService),
):
    return await service.get_suite(suite_id)


@router.patch(
    "/suites/{suite_id}",
    response_model=TestSuite,
    dependencies=[Depends(auth), Depends(permissions(P.Workflow.UPDATE))],
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
    dependencies=[Depends(auth), Depends(permissions(P.Workflow.UPDATE))],
)
async def delete_test_suite(
    suite_id: UUID,
    service: TestSuiteService = Injected(TestSuiteService),
):
    await service.delete_suite(suite_id)


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
    return await service.import_cases_from_conversation(suite_id, data.conversation_id, data.replace)


@router.post(
    "/suites/{suite_id}/runs",
    response_model=TestRun,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(auth), Depends(permissions(P.Workflow.TEST))],
)
async def run_test_suite(
    suite_id: UUID,
    data: TestRunCreate,
    service: TestSuiteService = Injected(TestSuiteService),
):
    """
    Execute all test cases in the suite against the configured workflow and
    evaluate with the requested techniques.
    """
    return await service.start_run(suite_id, data)


@router.get(
    "/suites/{suite_id}/runs",
    response_model=List[TestRun],
    dependencies=[Depends(auth), Depends(permissions(P.Workflow.READ))],
)
async def list_runs_for_suite(
    suite_id: UUID,
    service: TestSuiteService = Injected(TestSuiteService),
):
    return await service.list_runs_for_suite(suite_id)


@router.get(
    "/runs/{run_id}",
    response_model=TestRun,
    dependencies=[Depends(auth), Depends(permissions(P.Workflow.READ))],
)
async def get_run(
    run_id: UUID,
    service: TestSuiteService = Injected(TestSuiteService),
):
    return await service.get_run(run_id)


@router.get(
    "/runs/{run_id}/results",
    response_model=List[TestResult],
    dependencies=[Depends(auth), Depends(permissions(P.Workflow.READ))],
)
async def list_results_for_run(
    run_id: UUID,
    service: TestSuiteService = Injected(TestSuiteService),
):
    return await service.list_results_for_run(run_id)


# ---------------------------------------------------------------------------
# Evaluations
# ---------------------------------------------------------------------------

@router.get(
    "/evaluations",
    response_model=List[TestEvaluation],
    dependencies=[Depends(auth), Depends(permissions(P.Workflow.READ))],
)
async def list_evaluations(
    service: TestSuiteService = Injected(TestSuiteService),
):
    return await service.list_evaluations()


@router.post(
    "/evaluations",
    response_model=TestEvaluation,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(auth), Depends(permissions(P.Workflow.UPDATE))],
)
async def create_evaluation(
    data: TestEvaluationCreate,
    service: TestSuiteService = Injected(TestSuiteService),
):
    return await service.create_evaluation(data)


@router.get(
    "/evaluations/{evaluation_id}",
    response_model=TestEvaluation,
    dependencies=[Depends(auth), Depends(permissions(P.Workflow.READ))],
)
async def get_evaluation(
    evaluation_id: UUID,
    service: TestSuiteService = Injected(TestSuiteService),
):
    return await service.get_evaluation(evaluation_id)


@router.patch(
    "/evaluations/{evaluation_id}",
    response_model=TestEvaluation,
    dependencies=[Depends(auth), Depends(permissions(P.Workflow.UPDATE))],
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
    dependencies=[Depends(auth), Depends(permissions(P.Workflow.UPDATE))],
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
    dependencies=[Depends(auth), Depends(permissions(P.Workflow.UPDATE))],
)
async def delete_evaluation(
    evaluation_id: UUID,
    service: TestSuiteService = Injected(TestSuiteService),
):
    await service.delete_evaluation(evaluation_id)

