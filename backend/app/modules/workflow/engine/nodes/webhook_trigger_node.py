"""Webhook Trigger node: the entry point for externally started workflow runs.

The public ingress (``/webhook/execute/{id}``) has already authenticated the
delivery, mapped it onto the engine input and queued the run by the time this
node executes, so at run time the node only re-applies the mapping over the
``webhook`` envelope it finds on the state and hands the result downstream.

When there is no envelope on the state the run was started from the builder's
Test button or a schedule, and the node falls back to its configured sample
payload so the rest of the workflow can still be exercised.
"""

import logging
from typing import Any, Dict

from app.modules.workflow.engine.base_node import BaseNode
from app.modules.workflow.engine.node_result import node_failure
from app.modules.workflow.webhook_trigger_mapping import (
    ENVELOPE_KEY,
    build_envelope,
    build_trigger_input,
    parse_sample_payload,
)

logger = logging.getLogger(__name__)


class WebhookTriggerNode(BaseNode):
    """Turns an inbound HTTP delivery into the workflow's input."""

    def _unresolved_config_fields(self) -> set[str]:
        # Paths and sample JSON are data, not templates: never substitute `${...}`.
        return {"fieldMappings", "messagePath", "threadIdPath", "idempotencyPath", "samplePayload"}

    async def process(self, config: Dict[str, Any]) -> Any:  # pylint: disable=unused-argument
        envelope = self.get_state().get_value(ENVELOPE_KEY)
        if not isinstance(envelope, dict):
            envelope = build_envelope(
                method="POST",
                headers={},
                query={},
                body=parse_sample_payload(self.node_data),
                is_test=True,
            )
            logger.info("WebhookTriggerNode %s has no delivery on state; using the sample payload", self.node_id)

        input_data, errors = build_trigger_input(envelope, self.node_data)
        if errors:
            # Ingress validates live deliveries, so this only happens for a test
            # run or when the workflow was edited after the run was queued.
            return node_failure("; ".join(errors), code=422)

        self.set_node_input(input_data)
        return input_data
