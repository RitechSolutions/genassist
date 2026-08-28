"""Frame routing for sub-agent turns, shared by every interactive surface"""

import asyncio
import logging
from typing import Optional

from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.modules.workflow.agents.sub_agents import messages
from app.modules.workflow.usage_context import WorkflowUsageContext

logger = logging.getLogger(__name__)


class SubAgentTurnRouter:
    """Routes a turn into an active sub-agent frame and resumes the parent on completion"""

    def __init__(self, workflow_engine, owner_id: str):
        self.workflow_engine = workflow_engine
        self.owner_id = owner_id

    def has_sub_agents(self) -> bool:
        return any(n.get("type") == "subAgentNode" for n in self.workflow_engine.workflow.get("nodes", []))

    async def route_turn(
        self,
        session_message: str,
        thread_id: str,
        input_data: dict,
        persist: bool,
        usage_context: Optional[WorkflowUsageContext] = None,
    ) -> Optional[dict]:
        """Route a turn into an active sub-agent, or return None to run the root flow.

        ``usage_context`` (built by the caller before routing) attributes LLM usage
        for the resumed child and parent runs to the ledger.
        """
        from app.modules.workflow.agents.memory import ConversationMemory
        from app.modules.workflow.agents.sub_agents import graph as sub_graph
        from app.modules.workflow.agents.sub_agents import session as sub_session

        memory = ConversationMemory.get_instance(thread_id=thread_id)
        try:
            stack = await sub_session.read_frame_strict(memory)
        except sub_session.SubAgentSessionError:
            return self._plain_message(messages.CONVERSATION_UNRESUMABLE)

        if stack is None:
            return None

        workflow_id = str(self.workflow_engine.workflow_id)
        if not sub_session.is_owned(stack, self.owner_id, workflow_id):
            return None

        workflow = self.workflow_engine.workflow
        current_fp = sub_graph.fingerprint(workflow.get("nodes", []), workflow.get("edges", []))
        if stack.top().workflow_fingerprint != current_fp:
            await sub_session.clear_stack(memory)
            raise AppException(ErrorKey.SUB_AGENT_SESSION_STALE, status_code=409)

        return await self._run_active_child(
            session_message, thread_id, input_data, persist, memory, stack, usage_context
        )

    async def _run_active_child(
        self, session_message, thread_id, input_data, persist, memory, stack, usage_context=None
    ):
        from app.modules.workflow.agents.sub_agents import orchestrator
        from app.modules.workflow.agents.sub_agents import session as sub_session
        from app.modules.workflow.agents.sub_agents.models import SUB_AGENT_RESUME_KEY, SubAgentStack

        frame = stack.top()
        timeout_seconds = self._child_timeout(frame.child_node_id)
        try:
            child_state = await orchestrator.run_child_turn(
                workflow=self.workflow_engine.workflow,
                root_thread_id=thread_id,
                child_node_id=frame.child_node_id,
                invocation_id=frame.invocation_id,
                message=session_message,
                session=input_data.get("session"),
                timeout_seconds=timeout_seconds,
                inherit_pii=frame.inherit_pii,
                usage_context=usage_context,
            )
        except asyncio.TimeoutError:
            return self._plain_message(messages.child_timeout(timeout_seconds, retry=True))
        except Exception:
            logger.exception("Sub-agent resume turn for %s failed", frame.child_node_id)
            return self._plain_message(messages.child_failed(retry=True))

        completion = orchestrator.child_completion(child_state)
        if completion is None:
            response = child_state.format_state_as_response()
            if self._is_awaiting_sub_agent(response.get("output")):
                return self.finalize(response)
            return self._message_only(response, orchestrator.child_message(child_state))

        remaining = stack.frames[:-1]
        if remaining:
            await sub_session.write_frame(memory, SubAgentStack(agent_id=stack.agent_id, frames=remaining))
        else:
            await sub_session.clear_stack(memory)
        orchestrator.discard_child_memory(thread_id, frame.child_node_id, frame.invocation_id)

        resume = {
            **frame.parent_resume.model_dump(),
            "child_node_id": frame.child_node_id,
            "mode": frame.mode,
            "child_task": frame.task,
            "child_result": completion.get("result", orchestrator.child_message(child_state)),
            **self._child_trace(child_state, frame.child_node_id),
        }
        state = await self.workflow_engine.execute_from_node(
            start_node_id=frame.parent_node_id,
            input_data={**input_data, SUB_AGENT_RESUME_KEY: resume},
            thread_id=thread_id,
            persist=persist,
            registry_managed=True,
            usage_context=usage_context,
        )
        orchestrator.propagate_prompt_cache_diagnostics(child_state, state)
        return self.finalize(state.format_state_as_response())

    def _child_timeout(self, child_node_id: str) -> float:
        from app.modules.workflow.agents.sub_agents.graph import DEFAULT_CHILD_TIMEOUT_SECONDS, child_timeout_seconds

        for node in self.workflow_engine.workflow.get("nodes", []):
            if node.get("id") == child_node_id:
                return child_timeout_seconds(node.get("data", {}))
        return DEFAULT_CHILD_TIMEOUT_SECONDS

    def finalize(self, response: dict) -> dict:
        """Turn a sub-agent “waiting” pause into a normal success message so the plugin
        doesn't show an empty form"""
        output = response.get("output")
        if self._is_awaiting_sub_agent(output):
            return self._message_only(response, (output.get("sub_agent") or {}).get("message", ""))
        return response

    @staticmethod
    def _is_awaiting_sub_agent(output) -> bool:
        return isinstance(output, dict) and output.get("status") == "awaiting_input" and "sub_agent" in output

    def _message_only(self, response: dict, text: str) -> dict:
        """Reduce a child response to a plain success message"""
        message = {"message": text}
        response["status"] = "success"
        response["output"] = message
        state = response.get("state")
        if isinstance(state, dict) and isinstance(state.get("output"), dict):
            state["output"] = dict(message)
        return response

    @staticmethod
    def _child_trace(child_state, child_id: str) -> dict:
        """Bounded child step/tool trace for the parent's resume marker; empty if unavailable"""
        from app.modules.workflow.engine.nodes.agent_node import SUB_AGENT_TRACE_STEPS_CAP

        output = getattr(child_state, "node_outputs", {}).get(child_id)
        if not isinstance(output, dict):
            return {}
        steps = output.get("steps")
        tools_used = output.get("tools_used")
        return {
            "child_steps": steps[-SUB_AGENT_TRACE_STEPS_CAP:] if isinstance(steps, list) else [],
            "child_tools_used": tools_used[-SUB_AGENT_TRACE_STEPS_CAP:] if isinstance(tools_used, list) else [],
        }

    def _plain_message(self, message: str) -> dict:
        return {"status": "success", "output": {"message": message}, "token_usage": {}, "cost_usd": 0.0}
