"""Celery task executing a workflow run queued by a Webhook Trigger delivery.

Mirrors ``workflow_schedule_tasks.execute_workflow_run_async``. The tenant is
known at enqueue time, so the task runs for that single tenant instead of
scanning every tenant for the run row.
"""

import logging
from uuid import UUID

from celery import shared_task

from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.core.tenant_scope import get_tenant_context
from app.core.utils.enums.workflow_schedule_enum import WorkflowScheduleRunStatus
from app.core.utils.uuid_utils import coerce_uuid
from app.db.multi_tenant_session import multi_tenant_manager
from app.dependencies.injector import injector
from app.modules.websockets.socket_connection_manager import SocketConnectionManager
from app.modules.workflow.usage_context import WorkflowUsageContext
from app.repositories.agent import AgentRepository
from app.repositories.webhook_repository import WebhookRepository
from app.repositories.workflow_trigger_run import WorkflowTriggerRunRepository
from app.services.realtime_notifications import emit_notification, notification_payload
from app.tasks.base import (
    ABANDONED_RUN_ERROR,
    run_async_in_celery,
    run_task_for_tenant,
    should_execute_run,
    was_abandoned_by_worker,
)

logger = logging.getLogger(__name__)

TRIGGER_NODE_TYPE = "webhookTriggerNode"


def _notify_run_failed(tenant_id: str, run_id: UUID) -> None:
    emit_notification(
        socket_connection_manager=injector.get(SocketConnectionManager),
        tenant_id=tenant_id,
        payload=notification_payload(
            notification_id=f"workflow_failed:webhook:{run_id}",
            title="Webhook Trigger Run Failed",
            description=f"Webhook-triggered run {str(run_id)[:8]}... failed.",
            level="error",
            action_url="/ai-agents",
            entity_kind="workflow_trigger_run",
            entity_id=run_id,
            event_key=f"workflow_failed:webhook:{run_id}",
        ),
    )


def _engine_error_message(state) -> str:
    messages = []
    for entry in getattr(state, "errors", None) or []:
        if isinstance(entry, dict):
            messages.append(str(entry.get("message") or entry.get("error") or entry))
        else:
            messages.append(str(entry))
    return "; ".join(m for m in messages if m) or "Workflow execution failed"


async def execute_webhook_trigger_run_async(run_id: UUID):
    tenant_id = get_tenant_context()
    session_factory = multi_tenant_manager.get_tenant_session_factory(tenant_id)

    async with session_factory() as session:
        try:
            run_repository = WorkflowTriggerRunRepository(session)
            webhook_repository = WebhookRepository(session)
            agent_repository = AgentRepository(session)

            try:
                try:
                    run = await run_repository.get_by_id(run_id)
                except AppException as e:
                    if e.error_key == ErrorKey.NOT_FOUND:
                        logger.warning("Webhook trigger run %s not found in tenant %s", run_id, tenant_id)
                        return None
                    raise
                if not should_execute_run("Webhook trigger run", run_id, run.status):
                    if was_abandoned_by_worker(run.status):
                        await run_repository.update_status(
                            run_id, WorkflowScheduleRunStatus.FAILED, error_message=ABANDONED_RUN_ERROR
                        )
                        await session.commit()
                        _notify_run_failed(tenant_id, run_id)
                    return None

                await run_repository.update_status(run_id, WorkflowScheduleRunStatus.RUNNING)
                await session.commit()

                webhook = await webhook_repository.get_by_id(run.webhook_id)
                if not webhook or int(webhook.is_active or 0) != 1:
                    raise Exception("Trigger endpoint is disabled or deleted")

                # Always the agent's CURRENT workflow, like schedules.
                agent = await agent_repository.get_by_id_full(run.agent_id)
                if not agent or not agent.workflow:
                    raise Exception(f"Agent {run.agent_id} has no associated workflow")
                workflow = agent.workflow
                node = next(
                    (n for n in (workflow.nodes or []) if n.get("id") == run.node_id and n.get("type") == TRIGGER_NODE_TYPE),
                    None,
                )
                if node is None:
                    raise Exception("Trigger node is no longer part of the agent's workflow")

                input_data = dict(run.input_data or {})
                thread_id = run.thread_id or str(run.id)
                input_data["thread_id"] = thread_id

                workflow_config = {
                    "id": str(workflow.id),
                    "nodes": workflow.nodes or [],
                    "edges": workflow.edges or [],
                }
                # Imported lazily so the worker master never loads ML libs before forking
                from app.modules.workflow.engine.workflow_engine import WorkflowEngine
                from app.tasks.workflow_schedule_tasks import _redact_structure

                workflow_engine = WorkflowEngine(workflow_config)
                state = await workflow_engine.execute_from_node(
                    start_node_id=run.node_id,
                    input_data=input_data,
                    thread_id=thread_id,
                    usage_context=WorkflowUsageContext(
                        source="webhook",
                        agent_id=coerce_uuid(run.agent_id),
                        workflow_id=coerce_uuid(workflow.id),
                    ),
                )
                execution_output = _redact_structure(state.format_state_as_response())
                execution_id = UUID(state.execution_id) if state.execution_id else None

                if getattr(state, "status", None) == "failed":
                    await run_repository.update_status(
                        run_id,
                        WorkflowScheduleRunStatus.FAILED,
                        error_message=_engine_error_message(state),
                        execution_output=execution_output,
                        execution_id=execution_id,
                        workflow_id=workflow.id,
                        thread_id=thread_id,
                    )
                    await session.commit()
                    _notify_run_failed(tenant_id, run_id)
                    logger.warning("Webhook trigger run %s finished with engine failure", run_id)
                    return None

                await run_repository.update_status(
                    run_id,
                    WorkflowScheduleRunStatus.COMPLETED,
                    execution_output=execution_output,
                    execution_id=execution_id,
                    workflow_id=workflow.id,
                    thread_id=thread_id,
                )
                await session.commit()
                logger.info("Webhook trigger run %s completed", run_id)

            except Exception as e:
                logger.error("Error executing webhook trigger run %s: %s", run_id, e, exc_info=True)
                try:
                    await session.rollback()
                    await run_repository.update_status(
                        run_id, WorkflowScheduleRunStatus.FAILED, error_message=str(e)
                    )
                    await session.commit()
                    _notify_run_failed(tenant_id, run_id)
                except Exception as update_error:  # pylint: disable=broad-except
                    logger.error("Error updating webhook trigger run status: %s", update_error)
        finally:
            await session.close()


async def execute_webhook_trigger_run_for_tenant(run_id: UUID, tenant_id: str):
    async def _run(**kwargs):
        return await execute_webhook_trigger_run_async(kwargs["run_id"])

    return await run_task_for_tenant(_run, "webhook trigger run", tenant_id, run_id=run_id)


@shared_task(name="execute_webhook_trigger_run")
def execute_webhook_trigger_run_task(run_id: str, tenant_id: str | None = None):
    """Celery task: execute one webhook-triggered workflow run in its tenant."""
    logger.info("Starting webhook trigger run %s for tenant %s", run_id, tenant_id)
    try:
        run_async_in_celery(
            execute_webhook_trigger_run_for_tenant(UUID(run_id), tenant_id or "master"),
            timeout=2 * 60 * 60,
            task_name=f"execute_webhook_trigger_run[{run_id}]",
        )
    except Exception as e:
        logger.error("Error in webhook trigger run task %s: %s", run_id, e, exc_info=True)
        raise
