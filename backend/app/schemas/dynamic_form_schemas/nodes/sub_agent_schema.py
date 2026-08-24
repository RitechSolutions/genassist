from typing import List

from ..base import FieldSchema
from ._memory_fields import memory_trimming_fields

SUB_AGENT_NODE_DIALOG_SCHEMA: List[FieldSchema] = [
    FieldSchema(
        name="name",
        type="text",
        label="Node Name",
        required=False,
        description="Names the delegation tool the parent agent sees (e.g. 'flight_search').",
    ),
    FieldSchema(
        name="providerId",
        type="select",
        label="LLM Provider",
        required=True,
    ),
    FieldSchema(
        name="description",
        type="text",
        label="Delegation Description",
        required=True,
        description="What this sub-agent handles. Surfaced to the parent agent so it knows when to delegate.",
    ),
    FieldSchema(
        name="mode",
        type="select",
        label="Collaboration Mode",
        required=True,
        default="single_turn",
        options=[
            {"value": "single_turn", "label": "Single Turn (answer and return)"},
            {"value": "task", "label": "Task (may clarify, then finish_task)"},
            {"value": "chat", "label": "Chat (owns turns until return_to_parent)"},
        ],
        description=(
            "single_turn returns one answer to the parent; task may ask the user one "
            "clarifying question before calling finish_task; chat takes over the conversation "
            "until it calls return_to_parent."
        ),
    ),
    FieldSchema(
        name="fallbackChainId",
        type="select",
        label="Fallback Chain",
        required=False,
        description="Optional ordered list of backup providers to try if the primary fails (timeouts, rate limits, service errors).",
    ),
    FieldSchema(
        name="systemPrompt",
        type="text",
        label="System Prompt",
        required=False,
        default="You are a helpful specialist sub-agent.",
    ),
    FieldSchema(
        name="type",
        type="select",
        label="Agent Type",
        required=False,
        default="ToolSelector",
        options=[
            {"value": "ToolSelector", "label": "Tool Selector"},
            {"value": "ReActAgent", "label": "ReAct"},
            {"value": "ReActAgentLC", "label": "ReAct (LangChain)"},
        ],
    ),
    FieldSchema(
        name="maxIterations",
        type="number",
        label="Max Iterations",
        required=False,
        default=7,
        min=1,
        step=1,
    ),
    FieldSchema(
        name="timeoutSeconds",
        type="number",
        label="Timeout (seconds)",
        required=False,
        default=120,
        min=5,
        max=300,
        step=5,
        description="How long the parent waits for one delegated turn before giving up.",
    ),
    FieldSchema(
        name="memory",
        type="boolean",
        label="Enable Memory",
        required=False,
        default=True,
    ),
    FieldSchema(
        name="piiMasking",
        type="boolean",
        label="Enable PII Masking",
        required=False,
        default=False,
        description=(
            "Mask PII before sending text to the LLM. When the parent masks, the child "
            "inherits masking and unmasks with its own map so its tools still get real values."
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
    *memory_trimming_fields(max_messages_default=20),
]
