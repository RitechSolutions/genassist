from typing import List

from ..base import ConditionalField, FieldSchema

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
        name="memoryTrimmingMode",
        type="select",
        label="Memory Trimming Mode",
        required=False,
        default="message_count",
        options=[
            {"value": "message_count", "label": "Last N Messages"},
            {"value": "token_budget", "label": "Token Budget"},
            {"value": "message_compacting", "label": "Message Compacting"},
            {"value": "rag_retrieval", "label": "RAG Retrieval"}
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
        description="Maximum messages when using message count mode",
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
            field="memoryTrimmingMode",
            value="message_compacting"
        )
    ),
    FieldSchema(
        name="compactingKeepRecent",
        type="number",
        label="Recent Messages to Keep",
        required=False,
        default=10,
        min=5,
        max=50,
        step=5,
        description="Number of recent messages to include in context (older messages are compacted)",
        conditional=ConditionalField(
            field="memoryTrimmingMode",
            value="message_compacting"
        )
    ),
    FieldSchema(
        name="compactingModel",
        type="select",
        label="Compacting Model",
        required=False,
        description="LLM provider to use for compaction (defaults to node's provider)",
        conditional=ConditionalField(
            field="memoryTrimmingMode",
            value="message_compacting"
        )
    ),
    FieldSchema(
        name="compactingImportantEntities",
        type="tags",
        label="Important Entities to Preserve",
        required=False,
        description="Entities that must always be retained in the compaction summary (e.g. 'client name', 'project ID')",
        conditional=ConditionalField(
            field="memoryTrimmingMode",
            value="message_compacting"
        )
    ),
    FieldSchema(
        name="ragPassthroughThreshold",
        type="number",
        label="Passthrough Threshold (messages)",
        required=False,
        default=30,
        min=4,
        max=500,
        step=1,
        description="Number of messages below which ALL messages are passed verbatim (no RAG)",
        conditional=ConditionalField(
            field="memoryTrimmingMode",
            value="rag_retrieval"
        )
    ),
    FieldSchema(
        name="ragGroupSize",
        type="number",
        label="Group Size (messages)",
        required=False,
        default=4,
        min=2,
        max=20,
        step=2,
        description="Number of messages per indexed group (must be even; each pair = 1 Q&A exchange)",
        conditional=ConditionalField(
            field="memoryTrimmingMode",
            value="rag_retrieval"
        )
    ),
    FieldSchema(
        name="ragGroupOverlap",
        type="number",
        label="Group Overlap (messages)",
        required=False,
        default=2,
        min=0,
        max=18,
        step=1,
        description="Number of overlapping messages between consecutive groups (must be less than group size)",
        conditional=ConditionalField(
            field="memoryTrimmingMode",
            value="rag_retrieval"
        )
    ),
    FieldSchema(
        name="ragQueryContextMessages",
        type="number",
        label="Query Context Messages",
        required=False,
        default=3,
        min=1,
        max=10,
        step=1,
        description="Number of recent messages combined with current message for a richer retrieval query",
        conditional=ConditionalField(
            field="memoryTrimmingMode",
            value="rag_retrieval"
        )
    ),
    FieldSchema(
        name="ragTopK",
        type="number",
        label="Retrieved Groups (top-k)",
        required=False,
        default=3,
        min=1,
        max=10,
        step=1,
        description="Maximum number of historical groups to retrieve from the vector store",
        conditional=ConditionalField(
            field="memoryTrimmingMode",
            value="rag_retrieval"
        )
    ),
    FieldSchema(
        name="ragRecentMessages",
        type="number",
        label="Recent Messages (verbatim)",
        required=False,
        default=6,
        min=2,
        max=50,
        step=2,
        description="Most recent messages always included verbatim in context alongside retrieved groups",
        conditional=ConditionalField(
            field="memoryTrimmingMode",
            value="rag_retrieval"
        )
    ),
    FieldSchema(
        name="ragMaxHistoryHours",
        type="number",
        label="Max History Age (hours)",
        required=False,
        default=100000,
        min=0,
        max=100_000,
        step=1,
        description="Exclude retrieved groups older than this many hours. Set to 0 to disable (no age limit).",
        conditional=ConditionalField(
            field="memoryTrimmingMode",
            value="rag_retrieval"
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
