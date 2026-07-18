"""Registry for managing initialized agents"""

import logging
from typing import Optional, Union

from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.db.models import AgentModel
from app.schemas.agent import AgentRead

logger = logging.getLogger(__name__)


class RegistryItem:
    """
    Item in the registry.

    Accepts either AgentModel (SQLAlchemy) or AgentRead (Pydantic).
    AgentRead is preferred for better performance (already has workflow dict).
    """

    def __init__(self, agent: Union[AgentModel, AgentRead]):
        # Handle both SQLAlchemy and Pydantic models
        if isinstance(agent, AgentRead):
            # Pydantic model - workflow dict is already present
            self.agent_id = str(agent.id)
            self.agent_name = agent.name
            self.workflow_model = agent.workflow
        else:
            # SQLAlchemy model - extract workflow dict
            self.agent_id = str(agent.id)
            self.agent_name = agent.name
            self.workflow_model = agent.workflow.to_dict() if agent.workflow else None

        from app.modules.workflow.engine.workflow_engine import WorkflowEngine

        # Only create workflow engine if workflow exists
        if self.workflow_model is not None:
            self.workflow_engine = WorkflowEngine(self.workflow_model)
            logger.debug(f"Workflow model: {self.workflow_model}")
        else:
            self.workflow_engine = None
            logger.warning(f"Agent {self.agent_name} ({self.agent_id}) has no workflow assigned")

    def _has_sub_agents(self) -> bool:
        return any(n.get("type") == "subAgentNode" for n in self.workflow_model.get("nodes", []))

    async def execute(self, session_message: str, metadata: dict, persist: bool = True) -> dict:
        """Execute a workflow, optionally resuming from a specific node.

        persist=False skips writing this turn to conversation memory (used by the
        start greeting trigger so its synthetic instruction isn't kept in history).
        """
        if self.workflow_engine is None:
            raise ValueError(
                f"Cannot execute workflow for agent {self.agent_name} ({self.agent_id}): "
                f"No workflow is assigned to this agent"
            )

        thread_id = metadata.get("thread_id", None)
        start_node_id = metadata.get("human_in_the_loop_node_id")

        input_data = {"message": session_message, **metadata}

        # Sub-agent delegation only kicks in for workflows that have sub-agents; a
        # HITL resume (client-driven) always takes precedence over frame routing
        if self._has_sub_agents():
            input_data["agent_id"] = self.agent_id
            if not start_node_id and thread_id:
                routed = await self._route_sub_agent_turn(session_message, thread_id, input_data, persist)
                if routed is not None:
                    return routed

        state = await self.workflow_engine.execute_from_node(
            start_node_id=start_node_id,
            input_data=input_data,
            thread_id=thread_id,
            persist=persist,
            registry_managed=True,
        )
        return self._finalize_response(state.format_state_as_response())

    async def _route_sub_agent_turn(
        self, session_message: str, thread_id: str, input_data: dict, persist: bool
    ) -> Optional[dict]:
        """Route a turn into an active sub-agent, or return None to run the root flow"""
        from app.modules.workflow.agents.memory import ConversationMemory
        from app.modules.workflow.agents.sub_agents import graph as sub_graph
        from app.modules.workflow.agents.sub_agents import session as sub_session

        memory = ConversationMemory.get_instance(thread_id=thread_id)
        try:
            stack = await sub_session.read_frame_strict(memory)
        except sub_session.SubAgentSessionError:
            return self._plain_message(
                "This conversation could not be resumed. Please start a new message."
            )

        if stack is None:
            return None

        workflow_id = str(self.workflow_engine.workflow_id)
        if not sub_session.is_owned(stack, self.agent_id, workflow_id):
            return None

        workflow = self.workflow_engine.workflow
        current_fp = sub_graph.fingerprint(workflow.get("nodes", []), workflow.get("edges", []))
        if stack.top().workflow_fingerprint != current_fp:
            await sub_session.clear_stack(memory)
            raise AppException(ErrorKey.SUB_AGENT_SESSION_STALE, status_code=409)

        return await self._run_active_child(session_message, thread_id, input_data, persist, memory, stack)

    async def _run_active_child(self, session_message, thread_id, input_data, persist, memory, stack):
        from app.modules.workflow.agents.sub_agents import orchestrator
        from app.modules.workflow.agents.sub_agents import session as sub_session
        from app.modules.workflow.agents.sub_agents.models import SubAgentStack

        frame = stack.top()
        child_state = await orchestrator.run_child_turn(
            workflow=self.workflow_engine.workflow,
            root_thread_id=thread_id,
            child_node_id=frame.child_node_id,
            invocation_id=frame.invocation_id,
            message=session_message,
            timeout_seconds=self._child_timeout(frame.child_node_id),
            inherit_pii=frame.inherit_pii,
        )

        completion = orchestrator.child_completion(child_state)
        if completion is None:
            return self._finalize_response(child_state.format_state_as_response())

        remaining = stack.frames[:-1]
        if remaining:
            await sub_session.write_frame(memory, SubAgentStack(agent_id=stack.agent_id, frames=remaining))
        else:
            await sub_session.clear_stack(memory)

        resume = {
            **frame.parent_resume.model_dump(),
            "child_node_id": frame.child_node_id,
            "mode": frame.mode,
            "child_task": frame.task,
            "child_result": completion.get("result", orchestrator.child_message(child_state)),
        }
        state = await self.workflow_engine.execute_from_node(
            start_node_id=frame.parent_node_id,
            input_data={**input_data, "__sub_agent_resume": resume},
            thread_id=thread_id,
            persist=persist,
            registry_managed=True,
        )
        return self._finalize_response(state.format_state_as_response())

    def _child_timeout(self, child_node_id: str) -> float:
        for node in self.workflow_engine.workflow.get("nodes", []):
            if node.get("id") == child_node_id:
                try:
                    return float(node.get("data", {}).get("timeoutSeconds", 120) or 120)
                except (TypeError, ValueError):
                    return 120.0
        return 120.0

    def _finalize_response(self, response: dict) -> dict:
        """Turn a sub-agent “waiting” pause into a normal success message so the plugin
        doesn't show an empty form"""
        output = response.get("output")
        if isinstance(output, dict) and output.get("status") == "awaiting_input" and "sub_agent" in output:
            message = {"message": (output.get("sub_agent") or {}).get("message", "")}
            response["status"] = "success"
            response["output"] = message
            state = response.get("state")
            if isinstance(state, dict) and isinstance(state.get("output"), dict):
                state["output"] = dict(message)
        return response

    def _plain_message(self, message: str) -> dict:
        return {"status": "success", "output": {"message": message}, "token_usage": {}, "cost_usd": 0.0}
