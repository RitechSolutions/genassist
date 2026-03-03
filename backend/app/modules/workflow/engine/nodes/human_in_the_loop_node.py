"""Human In The Loop node that collects user data via a dynamic form."""

from typing import Any, Dict
import logging

from app.modules.workflow.engine.base_node import BaseNode
from app.modules.workflow.engine.workflow_state import WorkflowPausedException

logger = logging.getLogger(__name__)


class HumanInTheLoopNode(BaseNode):
    """
    Collects user input via a dynamic form.

    On first execution (no form data available): returns form_schema as output
    with next_nodes=[] to halt the workflow. The caller re-executes the workflow
    from this node once the user submits the form.

    On resume (user submitted form data via human_in_the_loop_from_form in metadata):
    returns the submitted data for downstream nodes.
    """

    async def process(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process the human in the loop node.

        Priority order:
        1. Cached path (ask_once=True): data was already collected — return from memory.
        2. Submitted form data (human_in_the_loop_from_form in input_data) — return it.
        3. Provided values (from test dialog or pre-filled input_data) — return them.
        4. First time / ask_once=False: return form schema to request input.

        Config keys:
            form_fields: List of field definitions [{name, type, label, required, ...}]
            message: Optional message to display above the form
            ask_once: If True (default), collect input once and cache for subsequent executions.
                      If False, always show the form.
        """
        ask_once = config.get("ask_once", True)

        # 1. Check if data was already collected in a previous execution (only when ask_once)
        if ask_once:
            node_key = f"human_in_the_loop:{self.node_id}"
            cached = await self.get_memory().get_metadata(node_key)
            if cached is not None:
                logger.info(f"HumanInTheLoopNode {self.node_id}: using cached input from memory")
                return cached

        form_fields = config.get("form_fields", [])
        message = config.get("message", "Please provide the following information:")

        if not form_fields:
            raise ValueError(f"HumanInTheLoopNode {self.node_id}: no form fields configured")

        # 2. Check for submitted form data (from frontend form submission)
        # Only consume if the form data targets THIS node (avoids consuming data meant for another HumanInTheLoopNode)
        human_in_the_loop_from_form = self.state.initial_values.get("human_in_the_loop_from_form")
        human_in_the_loop_node_id = self.state.initial_values.get("human_in_the_loop_node_id")
        if human_in_the_loop_from_form is not None and human_in_the_loop_node_id == self.node_id:
            # Restore prior node outputs so downstream nodes can reference them
            paused_outputs = await self.get_memory().get_metadata("paused_node_outputs")
            if paused_outputs:
                self.get_state().node_outputs.update(paused_outputs)

            cancelled = self.state.initial_values.get("human_in_the_loop_cancelled", False)
            output_data = {**human_in_the_loop_from_form, "_cancelled": True} if cancelled else human_in_the_loop_from_form
            # Cache for ask_once
            if ask_once:
                await self.cache_user_input(human_in_the_loop_from_form)
            logger.info(f"HumanInTheLoopNode {self.node_id}: using submitted form data")
            return output_data

        # 3. Check for provided values (e.g. from test dialog)
        provided_values = self._extract_provided_values(form_fields)
        if provided_values:
            logger.info(f"HumanInTheLoopNode {self.node_id}: using provided input values")
            return provided_values

        # 4. Pause workflow — save state and raise exception to propagate through all layers
        await self.get_memory().set_metadata(
            "paused_node_outputs", self.get_state().node_outputs
        )

        form_schema = {
            "message": message,
            "fields": form_fields,
            "node_id": self.node_id,
        }

        logger.info(f"HumanInTheLoopNode {self.node_id}: requesting user input")
        raise WorkflowPausedException({
            "status": "awaiting_input",
            "form_schema": form_schema,
            "node_id": self.node_id,
        })

    def _extract_provided_values(self, form_fields: list) -> Dict[str, Any] | None:
        """Extract pre-filled values from initial_values (e.g. from test-node endpoint).

        Returns a dict of field values if ALL required fields are present in
        initial_values, None otherwise. Requiring all required fields prevents
        false matches against unrelated keys like "message" or "thread_id".
        """
        initial = self.state.initial_values or {}
        field_names = {f.get("name") for f in form_fields}
        required_names = {f.get("name") for f in form_fields if f.get("required", False)}

        matched = {k: v for k, v in initial.items() if k in field_names}

        # Only use provided values if all required fields are present
        # (when no fields are required, any matched value is sufficient)
        if not matched:
            return None
        if required_names and not required_names.issubset(matched.keys()):
            return None
        return matched

    async def cache_user_input(self, user_input_data: dict) -> None:
        """Cache user input data for ask_once behavior.

        Called after form submission to persist the user's response
        so subsequent executions skip the form.
        """
        if self.node_data.get("ask_once", True):
            node_key = f"human_in_the_loop:{self.node_id}"
            await self.get_memory().set_metadata(node_key, user_input_data)
            logger.info(f"HumanInTheLoopNode {self.node_id}: cached user input for ask_once")
