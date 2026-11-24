"""Celery task that fills a dataset with questions written from a knowledge base."""

import logging
from typing import Optional
from uuid import UUID

from celery import shared_task

from app.core.tenant_scope import background_task_context, clear_tenant_context, set_tenant_context
from app.tasks.base import create_task_wrapper, run_async_in_celery

logger = logging.getLogger(__name__)

TASK_NAME = "write_dataset_questions"


async def _write_questions(request) -> None:
    """Build the job from the tenant-scoped services; must run inside create_task_wrapper."""
    from app.core.utils.db_connection_utils import commit_scope_session
    from app.dependencies.dependency_injection import RedisString
    from app.dependencies.injector import injector
    from app.modules.data.manager import AgentRAGServiceManager
    from app.modules.workflow.llm.provider import LLMProvider
    from app.services.agent_knowledge import KnowledgeBaseService
    from app.services.generated_question_job import GeneratedQuestionJob
    from app.services.generated_question_runs import GeneratedQuestionRunStore
    from app.services.test_suite import TestSuiteService

    job = GeneratedQuestionJob(
        suite_service=injector.get(TestSuiteService),
        knowledge_service=injector.get(KnowledgeBaseService),
        rag_manager=injector.get(AgentRAGServiceManager),
        llm_provider=injector.get(LLMProvider),
        run_store=GeneratedQuestionRunStore(injector.get(RedisString)),
        commit=lambda: commit_scope_session(context=TASK_NAME),
    )
    await job.run(request)


@shared_task(name=TASK_NAME)
def write_dataset_questions_task(
    run_id: str,
    tenant_id: str,
    suite_id: str,
    knowledge_base_id: str,
    llm_provider_id: str,
    sample_size: Optional[int] = None,
) -> None:
    """Write questions from a knowledge base's articles and add them to a dataset."""
    from app.services.generated_question_job import TIME_LIMIT_SECONDS, QuestionRunRequest

    logger.info("Starting question run %s for dataset %s (tenant: %s)", run_id, suite_id, tenant_id)
    set_tenant_context(tenant_id)
    request = QuestionRunRequest(
        tenant_id=tenant_id,
        suite_id=UUID(suite_id),
        knowledge_base_id=UUID(knowledge_base_id),
        llm_provider_id=UUID(llm_provider_id),
        run_id=run_id,
        sample_size=sample_size,
    )
    with background_task_context():
        try:
            async def _run():
                async def task(**_kwargs):
                    await _write_questions(request)

                await create_task_wrapper(task)()

            run_async_in_celery(_run(), timeout=TIME_LIMIT_SECONDS, task_name=f"{TASK_NAME}[{run_id}]")
        except Exception as exc:
            logger.error("Error in question run %s: %s", run_id, exc, exc_info=True)
            raise
        finally:
            clear_tenant_context()
