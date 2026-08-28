from typing import List

from ..base import FieldSchema
from ._memory_fields import memory_trimming_fields

AGENT_NODE_DIALOG_SCHEMA: List[FieldSchema] = [
    FieldSchema(
        name="name",
        type="text",
        label="Node Name",
        required=False
    ),
    FieldSchema(
        name="providerId",
        type="select",
        label="LLM Provider",
        required=True
    ),
    FieldSchema(
        name="fallbackChainId",
        type="select",
        label="Fallback Chain",
        required=False,
        description="Optional ordered list of backup providers to try if the primary fails (timeouts, rate limits, service errors)."
    ),
    FieldSchema(
        name="systemPrompt",
        type="text",
        label="System Prompt",
        required=True,
        default="You are a helpful assistant that helps the user with their requests."
    ),
    FieldSchema(
        name="userPrompt",
        type="text",
        label="User Prompt",
        required=True,
        default="{{session.message}}"
    ),
    FieldSchema(
        name="type",
        type="select",
        label="Agent Type",
        required=True,
        default="ToolSelection"
    ),
    FieldSchema(
        name="maxIterations",
        type="number",
        label="Max Iterations",
        required=True,
        default=3
    ),
    FieldSchema(
        name="memory",
        type="boolean",
        label="Enable Memory",
        required=True
    ),
    FieldSchema(
        name="piiMasking",
        type="boolean",
        label="Enable PII Masking",
        required=False,
        default=False,
        description=(
            "Mask PII (emails, phones, national IDs, credit cards, IPs) before "
            "sending text to the LLM. Original values are restored in the response."
        ),
    ),
    FieldSchema(
        name="promptCaching",
        type="boolean",
        label="Enable Prompt Caching",
        required=False,
        default=False,
        description=(
            "Caches the stable start of the system prompt for 5 minutes so repeat calls "
            "read it at a reduced rate. Anthropic and Bedrock cache-capable models only."
        ),
    ),
    *memory_trimming_fields(max_messages_default=10),
]
