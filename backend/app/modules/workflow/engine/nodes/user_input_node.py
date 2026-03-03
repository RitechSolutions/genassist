"""User Input node that pauses workflow execution to collect user data via a form."""

from typing import Any, Dict
import logging

from app.modules.workflow.engine.base_node import BaseNode
from app.modules.workflow.engine.exceptions import WorkflowPausedException

logger = logging.getLogger(__name__)


class UserInputNode(BaseNode):
    """
    Pauses workflow to request user input via a dynamic form.

    On first execution: raises WorkflowPausedException with the form schema.
    On resume (after user submits): returns user input data for downstream nodes.
    """

    async def process(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process the user input node.

        Priority order:
        1. Cached path (ask_once=True): data was already collected — return from memory.
        2. Provided values (from test dialog or pre-filled input_data) — return them.
        3. First time / ask_once=False: pause and show the form.

        Note: The resume path after form submission is handled by
        WorkflowEngine.resume_from_pause(), which bypasses process() entirely
        and caches the data to memory when ask_once is enabled.

        Config keys:
            form_fields: List of field definitions [{name, type, label, required, ...}]
            message: Optional message to display above the form
            ask_once: If True (default), collect input once and cache for subsequent executions.
                      If False, always show the form.
        """
        ask_once = config.get("ask_once", True)

        # 1. Check if data was already collected in a previous execution (only when ask_once)
        if ask_once:
            node_key = f"user_input:{self.node_id}"
            cached = await self.get_memory().get_metadata(node_key)
            if cached is not None:
                logger.info(f"UserInputNode {self.node_id}: using cached input from memory")
                return cached

        form_fields = config.get("form_fields", [])
        message = config.get("message", "Please provide the following information:")

        if not form_fields:
            raise ValueError(f"UserInputNode {self.node_id}: no form fields configured")

        # 2. Check for provided values (e.g. from test dialog)
        provided_values = self._extract_provided_values(form_fields)
        if provided_values:
            logger.info(f"UserInputNode {self.node_id}: using provided input values")
            return provided_values

        # 3. Pause for input
        form_schema = {
            "message": message,
            "fields": form_fields,
            "node_id": self.node_id,
        }

        logger.info(f"UserInputNode {self.node_id}: pausing workflow for user input")
        raise WorkflowPausedException(
            node_id=self.node_id,
            form_schema=form_schema,
            message=message,
        )

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
        if required_names and required_names.issubset(matched.keys()):
            return matched

        return None

    async def cache_user_input(self, user_input_data: dict) -> None:
        """Cache user input data for ask_once behavior.

        Called by the engine after resume to persist the user's response
        so subsequent executions skip the form.
        """
        if self.node_data.get("ask_once", True):
            node_key = f"user_input:{self.node_id}"
            await self.get_memory().set_metadata(node_key, user_input_data)
            logger.info(f"UserInputNode {self.node_id}: cached user input for ask_once")
