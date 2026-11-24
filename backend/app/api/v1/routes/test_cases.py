from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, UploadFile, status
from fastapi_injector import Injected

from app.auth.dependencies import auth, permissions
from app.core.permissions.constants import Permissions as P
from app.core.tenant_scope import get_tenant_context
from app.dependencies.dependency_injection import RedisString
from app.dependencies.injector import injector
from app.modules.data.manager import AgentRAGServiceManager
from app.schemas.test_suite import (
    AddConversationToSuitesRequest,
    AddConversationToSuitesResult,
    ConversationSuiteMembership,
    ImportCasesFromConversationRequest,
    ImportCasesFromConversationsRequest,
    ImportCasesFromConversationsResult,
    ImportCasesFromFilesResult,
    TestCase,
    TestCaseCreate,
    TestCaseUpdate,
    WriteQuestionsEstimate,
    WriteQuestionsRequest,
    WriteQuestionsStatus,
)
from app.services.agent_knowledge import KnowledgeBaseService
from app.services.dataset_file import read_uploads
from app.services.generated_question_job import model_calls
from app.services.generated_question_runs import NOT_STARTED_ERROR, STATUS_FAILED, GeneratedQuestionRunStore
from app.services.llm_providers import LlmProviderService
from app.services.test_suite import TestSuiteService
from app.tasks.generated_question_tasks import write_dataset_questions_task


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


@router.post(
    "/suites/{suite_id}/cases/import-from-files/preview",
    response_model=ImportCasesFromFilesResult,
    dependencies=[Depends(auth), Depends(permissions(P.Workflow.READ))],
)
async def preview_cases_from_files(
    suite_id: UUID,
    files: List[UploadFile] = File(...),
    service: TestSuiteService = Injected(TestSuiteService),
):
    """Report what importing these dataset files would add, without saving anything."""
    return await service.preview_cases_from_files(suite_id, await read_uploads(files))


@router.post(
    "/suites/{suite_id}/cases/import-from-files",
    response_model=ImportCasesFromFilesResult,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(auth), Depends(permissions(P.Workflow.UPDATE))],
)
async def import_cases_from_files(
    suite_id: UUID,
    files: List[UploadFile] = File(...),
    service: TestSuiteService = Injected(TestSuiteService),
):
    """Add the conversations in these dataset files; unreadable files are reported, not fatal."""
    return await service.import_cases_from_files(suite_id, await read_uploads(files))


def _question_run_store() -> GeneratedQuestionRunStore:
    return GeneratedQuestionRunStore(injector.get(RedisString))


@router.get(
    "/suites/{suite_id}/cases/import-from-knowledge-base/estimate",
    response_model=WriteQuestionsEstimate,
    dependencies=[Depends(auth), Depends(permissions(P.Workflow.READ))],
)
async def estimate_cases_from_knowledge_base(
    suite_id: UUID,
    knowledge_base_id: UUID,
    sample_size: Optional[int] = None,
    service: TestSuiteService = Injected(TestSuiteService),
    knowledge_service: KnowledgeBaseService = Injected(KnowledgeBaseService),
):
    """How many articles a run could read from the knowledge base and the model calls it would make."""
    await service.get_suite(suite_id)
    knowledge_base = await knowledge_service.get_by_id(knowledge_base_id)
    document_ids = await injector.get(AgentRAGServiceManager).get_stored_document_ids(knowledge_base)
    return model_calls(len(document_ids), sample_size)


@router.post(
    "/suites/{suite_id}/cases/import-from-knowledge-base",
    response_model=WriteQuestionsStatus,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(auth), Depends(permissions(P.Workflow.UPDATE))],
)
async def write_cases_from_knowledge_base(
    suite_id: UUID,
    data: WriteQuestionsRequest,
    service: TestSuiteService = Injected(TestSuiteService),
    knowledge_service: KnowledgeBaseService = Injected(KnowledgeBaseService),
    llm_provider_service: LlmProviderService = Injected(LlmProviderService),
):
    """
    Start writing test questions from a knowledge base's articles.

    The run adds them to the dataset in the background; while one is in progress
    its state is returned and no second run starts.
    """
    await service.get_suite(suite_id)
    await knowledge_service.get_by_id(data.knowledge_base_id)
    await llm_provider_service.get_by_id(data.llm_provider_id)
    store, tenant = _question_run_store(), get_tenant_context()
    run_id = await store.claim(tenant, str(suite_id), str(data.knowledge_base_id))
    if run_id:
        try:
            write_dataset_questions_task.delay(
                run_id, tenant, str(suite_id), str(data.knowledge_base_id), str(data.llm_provider_id), data.sample_size
            )
        except Exception:
            await store.finish(tenant, str(suite_id), run_id, STATUS_FAILED, NOT_STARTED_ERROR)
            raise
    return await store.status(tenant, str(suite_id))


@router.get(
    "/suites/{suite_id}/cases/import-from-knowledge-base",
    response_model=WriteQuestionsStatus,
    dependencies=[Depends(auth), Depends(permissions(P.Workflow.READ))],
)
async def get_cases_from_knowledge_base_status(
    suite_id: UUID,
    service: TestSuiteService = Injected(TestSuiteService),
):
    """The question-writing run in progress on this dataset, else its last run's outcome."""
    await service.get_suite(suite_id)
    return await _question_run_store().status(get_tenant_context(), str(suite_id))


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