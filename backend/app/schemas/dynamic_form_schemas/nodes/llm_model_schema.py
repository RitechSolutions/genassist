from typing import List
from ..base import FieldSchema, ConditionalField

LLM_MODEL_NODE_DIALOG_SCHEMA: List[FieldSchema] = [
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
        name="systemPrompt",
        type="text",
        label="System Prompt",
        required=True
    ),
    FieldSchema(
        name="userPrompt",
        type="text",
        label="User Prompt",
        required=True
    ),
    FieldSchema(
        name="type",
        type="select",
        label="Type",
        required=True
    ),
    FieldSchema(
        name="memory",
        type="boolean",
        label="Enable Memory",
        required=True
    ),
    FieldSchema(
        name="memoryTrimmingMode",
        type="select",
        label="Memory Trimming Mode",
        required=False,
        default="message_count",
        options=[
            {"value": "message_count", "label": "Last N Messages"},
            {"value": "token_budget", "label": "Token Budget"}
        ],
        description="How to limit conversation history"
    ),
    FieldSchema(
        name="maxMessages",
        type="number",
        label="Max Messages",
        required=False,
        default=10,
        min=1,
        step=1,
        description="Maximum messages when using message count mode"
    ),
    FieldSchema(
        name="enableCompacting",
        type="boolean",
        label="Enable Message Compacting",
        required=False,
        default=False,
        description="Automatically compact older messages into summaries and entity stores",
        conditional=ConditionalField(
            field="memoryTrimmingMode",
            value="message_count"
        )
    ),
    FieldSchema(
        name="compactingThreshold",
        type="number",
        label="Compacting Threshold (messages)",
        required=False,
        default=20,
        min=10,
        max=100,
        step=5,
        description="Trigger compaction when total messages exceed this count",
        conditional=ConditionalField(
            field="enableCompacting",
            value=True
        )
    ),
    FieldSchema(
        name="compactingKeepRecent",
        type="number",
        label="Keep Recent Messages",
        required=False,
        default=10,
        min=5,
        max=50,
        step=5,
        description="Number of recent messages to keep uncompacted",
        conditional=ConditionalField(
            field="enableCompacting",
            value=True
        )
    ),
    FieldSchema(
        name="compactingModel",
        type="select",
        label="Compacting Model",
        required=False,
        description="LLM provider to use for compaction (defaults to node's provider)",
        conditional=ConditionalField(
            field="enableCompacting",
            value=True
        )
    ),
    FieldSchema(
        name="tokenBudget",
        type="number",
        label="Total Token Budget",
        required=False,
        default=10000,
        min=1000,
        max=50000,
        step=100,
        description="Total tokens available per request",
        conditional=ConditionalField(
            field="memoryTrimmingMode",
            value="token_budget"
        )
    ),
    FieldSchema(
        name="conversationHistoryTokens",
        type="number",
        label="Conversation History Allocation (tokens)",
        required=False,
        default=5000,
        min=0,
        max=20000,
        step=100,
        description="Token budget for conversation history",
        conditional=ConditionalField(
            field="memoryTrimmingMode",
            value="token_budget"
        )
    ),
]
