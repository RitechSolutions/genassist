"""Registry for managing initialized agents"""

import asyncio
import logging
from typing import Optional, Union

from starlette_context import context as request_context
from starlette_context.errors import ContextDoesNotExistError

from app.core.chat_turn_gate import chat_turn_gate
from app.core.utils.uuid_utils import coerce_uuid
from app.db.models import AgentModel
from app.modules.workflow.agents.sub_agents.turn_router import SubAgentTurnRouter
from app.modules.workflow.usage_context import WorkflowUsageContext
from app.schemas.agent import AgentRead

logger = logging.getLogger(__name__)


def _current_http_request():
    try:
        return request_context.get("http_request")
    except (LookupError, ContextDoesNotExistError):
        return None


class HttpClientWatch:
    """Notices an HTTP client leaving while its turn is queued. Non-HTTP callers are never gone.

    Starlette's ``Request.is_disconnected`` cannot see the disconnect behind BaseHTTPMiddleware,
    so this listens on the request's receive channel once the body has been consumed. Routes
    expose their request through ``expose_request_to_turn_gate`` in ``app.auth.dependencies``.
    """

    def __init__(self, request=None):
        self._request = request if request is not None else _current_http_request()
        self._task: Optional[asyncio.Task] = None

    def start(self) -> None:
        request = self._request
        body_consumed = getattr(request, "_stream_consumed", False)
        if request is None or not body_consumed:
            return
        self._task = asyncio.create_task(request.receive())

    async def client_gone(self) -> bool:
        task, self._task = self._task, None
        if task is None:
            return False
        if not task.done():
            task.cancel()
            return False
        if task.cancelled() or task.exception() is not None:
            return False
        return task.result().get("type") == "http.disconnect"

    def stop(self) -> None:
        if self._task is not None and not self._task.done():
            self._task.cancel()
        self._task = None


class RegistryItem:
    """Item in the registry"""

    def __init__(self, agent: Union[AgentModel, AgentRead]):
        if isinstance(agent, AgentRead):
            self.agent_id = str(agent.id)
            self.agent_name = agent.name
            self.workflow_model = agent.workflow
        else:
            self.agent_id = str(agent.id)
            self.agent_name = agent.name
            self.workflow_model = agent.workflow.to_dict() if agent.workflow else None

        from app.modules.workflow.engine.workflow_engine import WorkflowEngine

        # Only create workflow engine if workflow exists
        if self.workflow_model is not None:
            self.workflow_engine = WorkflowEngine(self.workflow_model)
            self._router = SubAgentTurnRouter(self.workflow_engine, owner_id=self.agent_id)
            logger.debug(f"Workflow model: {self.workflow_model}")
        else:
            self.workflow_engine = None
            self._router = None
            logger.warning(f"Agent {self.agent_name} ({self.agent_id}) has no workflow assigned")

    async def execute(self, session_message: str, metadata: dict, persist: bool = True, source: str = "chat") -> dict:
        """Run one agent turn behind the process-wide admission gate."""
        context = f"agent {self.agent_id} thread {metadata.get('thread_id')}"
        client_watch = HttpClientWatch()

        async def before_wait() -> None:
            client_watch.start()
            await self._release_idle_request_connection()

        try:
            async with chat_turn_gate.slot(context, before_wait=before_wait, caller_gone=client_watch.client_gone):
                return await self._execute_workflow(session_message, metadata, persist, source)
        finally:
            client_watch.stop()

    async def _release_idle_request_connection(self) -> None:
        """Return the request's pooled connection while queued, unless its transaction has writes."""
        # Local import avoids a circular import via the dependency injector.
        from app.core.utils.db_connection_utils import release_idle_connection

        await release_idle_connection(context=f"agent {self.agent_id}")

    async def _execute_workflow(
        self, session_message: str, metadata: dict, persist: bool = True, source: str = "chat"
    ) -> dict:
        """Execute a workflow, optionally resuming from a specific node.

        persist=False skips writing this turn to conversation memory (used by the
        start greeting trigger so its synthetic instruction isn't kept in history).
        ``source`` attributes recorded LLM usage.
        """
        if self.workflow_engine is None:
            raise ValueError(
                f"Cannot execute workflow for agent {self.agent_name} ({self.agent_id}): "
                f"No workflow is assigned to this agent"
            )

        thread_id = metadata.get("thread_id", None)
        start_node_id = metadata.get("human_in_the_loop_node_id")

        input_data = {"message": session_message, **metadata}

        # Build usage attribution before routing so resumed child and parent runs are captured
        usage_context = self._build_usage_context(source, thread_id)

        # Sub-agent delegation only kicks in for workflows that have sub-agents; a
        # HITL resume (client-driven) always takes precedence over frame routing
        if self._router.has_sub_agents():
            input_data["agent_id"] = self.agent_id
            if not start_node_id and thread_id:
                routed = await self._router.route_turn(
                    session_message, thread_id, input_data, persist, usage_context=usage_context
                )
                if routed is not None:
                    return routed

        state = await self.workflow_engine.execute_from_node(
            start_node_id=start_node_id,
            input_data=input_data,
            thread_id=thread_id,
            persist=persist,
            registry_managed=True,
            usage_context=usage_context,
        )
        return self._router.finalize(state.format_state_as_response())

    def _build_usage_context(self, source: str, thread_id):
        """Attribution for the usage ledger. Ids are validated (and NULLed) at record time"""
        return WorkflowUsageContext(
            source=source,
            agent_id=coerce_uuid(self.agent_id),
            workflow_id=coerce_uuid(getattr(self.workflow_engine, "workflow_id", None)),
            conversation_id=coerce_uuid(thread_id),
            defer_capture=True,
        )
