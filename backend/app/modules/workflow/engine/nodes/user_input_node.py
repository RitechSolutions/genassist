"""User Input node that pauses workflow execution to collect user data via a dynamic form."""

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
        2. Test mode: return sample data.
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

        # 3. Test execution — return sample data instead of pausing
        if self.state.is_test:
            logger.info(f"UserInputNode {self.node_id}: test mode, returning sample data")
            return self._generate_sample_output(form_fields)

        # 4. First execution — pause for input
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

    @staticmethod
    def _generate_sample_output(form_fields: list) -> Dict[str, Any]:
        """Generate sample output values based on field definitions."""
        sample_values = {
            "text": "Sample text",
            "number": 42,
            "select": None,  # handled per-field
            "boolean": True,
            "date": "2025-01-15",
        }
        result = {}
        for field in form_fields:
            field_type = field.get("type", "text")
            name = field.get("name", "unknown")
            if field_type == "select":
                options = field.get("options", [])
                result[name] = options[0]["value"] if options else "option_1"
            else:
                result[name] = sample_values.get(field_type, "sample")
        return result
