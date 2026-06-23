"""
Create Workflow Schedule tool node.

Lets a workflow (typically an agent, via a Tool Builder) create a recurring
workflow schedule at runtime — the same thing the Scheduling tab does manually.
"""

import json
import logging
from typing import Any, Dict
from uuid import UUID

from app.modules.workflow.engine.base_node import BaseNode
from app.core.utils.enums.workflow_schedule_enum import ThreadIdMode
from app.schemas.workflow_schedule import WorkflowScheduleCreate
from app.services.workflow_schedule import WorkflowScheduleService

logger = logging.getLogger(__name__)


class CreateWorkflowScheduleNode(BaseNode):
    """Creates a workflow schedule from the node configuration."""

    async def process(self, config: Dict[str, Any]) -> Any:
        """
        Expected (resolved) config:
            agentId: str          — agent whose latest workflow gets scheduled
            scheduleName: str     — schedule display name
            cronSchedule: str     — 5-field cron expression
            isActive: bool        — enable automatic runs (default True)
            threadIdMode: str     — "per_run" | "fixed" (default "per_run")
            fixedThreadId: str    — used when threadIdMode == "fixed"
            message: str          — message passed to the workflow input node
            inputData: dict|str   — optional extra input-node fields (object or JSON)
        """
        agent_id = config.get("agentId") or config.get("agent_id")
        # The schedule's own name — distinct from the node's name. Fall back to
        # the node name and then a default for resilience.
        name = (
            config.get("scheduleName")
            or config.get("schedule_name")
            or config.get("name")
            or "Scheduled Workflow"
        )
        cron_schedule = config.get("cronSchedule") or config.get("cron_schedule")
        is_active = config.get("isActive", True)
        thread_id_mode_raw = config.get("threadIdMode") or config.get(
            "thread_id_mode"
        ) or ThreadIdMode.PER_RUN.value
        fixed_thread_id = config.get("fixedThreadId") or config.get("fixed_thread_id")
        message = config.get("message")

        if not agent_id:
            return {"error": "agentId is required to create a workflow schedule"}
        if not cron_schedule:
            return {"error": "cronSchedule is required to create a workflow schedule"}

        # Build the input payload from message + any extra fields. The extra
        # fields may arrive as a dict or a JSON string (e.g. from a templated
        # config value), so handle both.
        input_data: Dict[str, Any] = {}
        extra = config.get("inputData") or config.get("input_data")
        if isinstance(extra, str) and extra.strip():
            try:
                extra = json.loads(extra)
            except json.JSONDecodeError:
                logger.warning("Create Schedule: inputData is not valid JSON; ignoring")
                extra = None
        if isinstance(extra, dict):
            input_data.update(extra)
        if message is not None:
            input_data["message"] = message

        try:
            thread_id_mode = ThreadIdMode(thread_id_mode_raw)
        except ValueError:
            thread_id_mode = ThreadIdMode.PER_RUN

        try:
            from app.dependencies.injector import injector

            schedule_service = injector.get(WorkflowScheduleService)
            created = await schedule_service.create(
                WorkflowScheduleCreate(
                    name=name,
                    agent_id=UUID(str(agent_id)),
                    cron_schedule=str(cron_schedule).strip(),
                    is_active=bool(is_active),
                    input_data=input_data or None,
                    thread_id_mode=thread_id_mode,
                    fixed_thread_id=fixed_thread_id,
                )
            )
            return {
                "status": "success",
                "schedule_id": str(created.id),
                "name": created.name,
                "cron_schedule": created.cron_schedule,
                "is_active": created.is_active,
                "message": f"Workflow schedule '{created.name}' created successfully.",
            }
        except Exception as e:
            error_msg = f"Error creating workflow schedule: {str(e)}"
            logger.error(error_msg)
            return {"error": error_msg}
