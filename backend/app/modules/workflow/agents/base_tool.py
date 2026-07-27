import inspect
import logging
import weakref
from typing import Any, Callable, Protocol

logger = logging.getLogger(__name__)


def to_snake_case(not_snake_case):
    final = ''
    for i in range(len(not_snake_case)):
        item = not_snake_case[i]
        next_char_will_be_underscored = False
        if i < len(not_snake_case) - 1:
            next_char_will_be_underscored = (
                not_snake_case[i+1] == "_" or
                not_snake_case[i+1] == " " or
                not_snake_case[i+1].isupper()
            )
        if (item == " " or item == "_") and next_char_will_be_underscored:
            continue
        elif (item == " " or item == "_"):
            final += "_"
        elif item.isupper():
            final += "_"+item.lower()
        else:
            final += item
    if final and final[0] == "_":
        final = final[1:]
    return final

class Tool(Protocol):
    """Protocol for tools"""
    name: str
    description: str
    
    def invoke(self, **kwargs) -> str:
        """Execute the tool with given arguments"""
        ...

class BaseTool(Tool):
    """Base class for tools"""
    def __init__(self, node_id: str, name: str, description: str, parameters: dict, function: Callable, return_direct: bool = False, agent_id: str = None, state: Any = None):
        self.node_id = node_id
        self.name = to_snake_case(name)
        self.description = description
        filtered_params = {k: v for k, v in parameters.items() if "session." not in k}
        self.parameters = filtered_params
        self.function = function
        self.return_direct = return_direct
        # Owning agent node and workflow state, bound when the tool is attached to
        # an agent, so each call can be recorded for evaluation.
        self.agent_id = agent_id
        self.state = state

    @property
    def state(self) -> Any:
        """The owning WorkflowState, held weakly so a tool never creates a
        reference cycle back into the state it is serialized inside."""
        return self._state_ref() if self._state_ref is not None else None

    @state.setter
    def state(self, value: Any) -> None:
        if value is None:
            self._state_ref = None
            return
        try:
            self._state_ref = weakref.ref(value)
        except TypeError:
            # Non-weak-referenceable (e.g. a test double): keep a plain reference.
            self._state_ref = lambda v=value: v

    async def invoke(self, **kwargs) -> Any:
        """Execute the tool with the given arguments.

        A tool's underlying function is a node's ``execute`` method. When that node
        fails it no longer raises — it returns a failure envelope (or an HTTP-error
        body / None). Detect that here and hand the agent an explicit error
        observation instead of the raw ``None``/error dict, so the agent does not
        silently treat the failure as success (e.g. claim a Zendesk ticket was
        created when it never was). Successful results pass through unchanged.
        """
        # Imported lazily to avoid any import-time coupling with the engine package.
        from app.modules.workflow.engine.node_result import is_node_failure

        try:
            result = self.function({"parameters": kwargs})
            if inspect.isawaitable(result):
                result = await result
        except Exception as exc:
            self._record_event(kwargs, None, status="failed", error=str(exc))
            raise

        failure = is_node_failure(result)
        if failure is not None:
            reason = failure.get("error") or "the tool did not complete its action"
            logger.warning("Tool '%s' (node %s) failed: %s", self.name, self.node_id, reason)
            self._record_event(kwargs, result, status="failed", error=reason)
            return (
                f"ERROR: the '{self.name}' tool did not complete successfully and no "
                f"action was taken. Reason: {reason}. Do not tell the user this "
                f"succeeded — report that it could not be completed."
            )
        self._record_event(kwargs, result, status="succeeded", error=None)
        return result

    def _record_event(self, arguments: dict, result: Any, *, status: str, error: str = None) -> None:
        """Record this call on the workflow state; never let telemetry break execution."""
        state = self.state
        if state is None or not hasattr(state, "add_tool_event"):
            return
        try:
            state.add_tool_event(
                agent_id=self.agent_id,
                tool_id=self.node_id,
                tool_name=self.name,
                arguments=arguments,
                result=result,
                status=status,
                error=error,
            )
        except Exception:
            logger.debug("Failed to record tool event for '%s'", self.name, exc_info=True)
