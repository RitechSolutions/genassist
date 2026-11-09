"""
Running a workflow test turn, shared by POST /workflows/test and the
background training job that runs such a test on the "ml" worker.

Both must behave the same: a turn on an existing thread is routed into an
active sub-agent first, and only a supplied thread is registry-managed
(thread continuations, persistent delegations).
"""

from typing import Any, Dict, Optional

from app.modules.workflow.agents.sub_agents.turn_router import SubAgentTurnRouter
from app.modules.workflow.usage_context import WorkflowUsageContext


async def run_workflow_test(
    workflow_engine,
    owner_id: str,
    input_data: Dict[str, Any],
    thread_id: str,
    start_node_id: Optional[str],
    usage_context: WorkflowUsageContext,
) -> Dict[str, Any]:
    """Run one test turn and return the response the test endpoint sends."""
    turn_router = SubAgentTurnRouter(workflow_engine, owner_id=owner_id)
    supplied_thread = bool(input_data.get("thread_id"))
    if turn_router.has_sub_agents():
        input_data.setdefault("agent_id", owner_id)
        if supplied_thread and not start_node_id:
            routed = await turn_router.route_turn(
                input_data.get("message", ""), thread_id, input_data, persist=True, usage_context=usage_context
            )
            if routed is not None:
                return routed

    state = await workflow_engine.execute_from_node(
        start_node_id=start_node_id,
        input_data=input_data,
        thread_id=thread_id,
        registry_managed=supplied_thread,
        usage_context=usage_context,
    )
    return turn_router.finalize(state.format_state_as_response())
