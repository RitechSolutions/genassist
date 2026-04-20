"""
Generate node_specs.md from the existing node schema definitions.

Usage:
    python -m app.db.seed.knowledge.generate_node_specs

This reads NODE_DIALOG_SCHEMAS, NODE_HANDLERS_SCHEMAS, and NODE_TYPE_LABELS
to produce a comprehensive markdown document describing every node type.
The output is written to app/db/seed/knowledge/node_specs.md.

Hand-authored descriptions and use cases are merged in from NODE_DESCRIPTIONS below.
"""

import os
from pathlib import Path

from app.schemas.dynamic_form_schemas.nodes import (
    NODE_DIALOG_SCHEMAS,
    NODE_HANDLERS_SCHEMAS,
    NODE_TYPE_LABELS,
)

# ── Hand-authored semantic metadata per node ──────────────────────────────────
# category, description, when_to_use, example_use_cases

NODE_DESCRIPTIONS = {
    "chatInputNode": {
        "category": "I/O",
        "description": "Entry point for chat-based workflows. Receives the user's message and passes it downstream.",
        "when_to_use": "Every chat-based workflow MUST start with this node. It captures the user's input.",
        "example_use_cases": [
            "Starting point for a customer support chatbot",
            "Receiving user queries in a Q&A assistant",
            "Capturing commands for an automation workflow triggered by chat",
        ],
    },
    "chatOutputNode": {
        "category": "I/O",
        "description": "Exit point for chat-based workflows. Sends the final response back to the user.",
        "when_to_use": "Every chat-based workflow MUST end with this node. It delivers the result to the user.",
        "example_use_cases": [
            "Returning the agent's final answer to the user",
            "Displaying formatted results after data processing",
            "Sending confirmation messages after an action is completed",
        ],
    },
    "agentNode": {
        "category": "AI",
        "description": "An LLM-powered agent that can reason, use tools, and hold multi-turn conversations. Supports ReAct, ToolSelector, SimpleToolExecutor, and ChainOfThought patterns.",
        "when_to_use": "When you need AI reasoning, tool calling, or conversational ability. This is the core 'brain' of most workflows.",
        "example_use_cases": [
            "Customer support chatbot with tool access",
            "Data analysis assistant that queries databases via tools",
            "Email classifier that routes to different actions",
        ],
    },
    "llmModelNode": {
        "category": "AI",
        "description": "A standalone LLM call node. Sends a system prompt + user prompt to a language model and returns the response. Similar to agentNode but without tool calling or ReAct loops.",
        "when_to_use": "When you need a simple LLM completion without agent behavior (no tools, no reasoning loops). Good for text generation, summarization, classification.",
        "example_use_cases": [
            "Summarizing a document or email",
            "Classifying text into categories",
            "Generating a response from a template-filled prompt",
        ],
    },
    "templateNode": {
        "category": "Processing",
        "description": "Formats text using a template with variable substitution. Variables use {{source.field}} or {{session.field}} syntax.",
        "when_to_use": "When you need to format or combine data from previous nodes into a specific text format before passing it downstream.",
        "example_use_cases": [
            "Formatting agent output before sending to chatOutputNode",
            "Building a structured prompt from multiple data sources",
            "Composing an email body from extracted data fields",
        ],
    },
    "routerNode": {
        "category": "Control Flow",
        "description": "Conditional branching node. Compares two values and routes to output_true or output_false. Supports conditions: equals, not_equals, contains, greater_than, less_than, etc.",
        "when_to_use": "When the workflow needs to branch based on a condition (e.g., route urgent vs. non-urgent items differently).",
        "example_use_cases": [
            "Routing high-priority tickets to Jira, low-priority to Slack",
            "Branching based on email sender domain",
            "Conditional processing based on classification results",
        ],
    },
    "aggregatorNode": {
        "category": "Control Flow",
        "description": "Collects outputs from multiple upstream nodes and combines them using a strategy (list, merge, first, last). Useful after branching to reconverge.",
        "when_to_use": "When multiple parallel branches need to be combined back into a single flow. Often used after routerNode branches rejoin.",
        "example_use_cases": [
            "Merging results from parallel API calls",
            "Collecting outputs from multiple tool executions",
            "Reconverging after a router's true/false branches",
        ],
    },
    "humanInTheLoopNode": {
        "category": "Control Flow",
        "description": "Pauses workflow execution and presents a form to the user for input. Resumes after the user submits. Enables human approval or data entry mid-workflow.",
        "when_to_use": "When a human needs to review, approve, or provide additional input before the workflow continues.",
        "example_use_cases": [
            "Manager approval before creating a Jira ticket",
            "User confirmation before sending an email",
            "Human review of AI-generated content before publishing",
        ],
    },
    "workflowExecutorNode": {
        "category": "Control Flow",
        "description": "Executes another workflow as a sub-workflow within the current workflow. Enables workflow composition and reuse.",
        "when_to_use": "When you want to call another existing workflow as a building block within a larger workflow.",
        "example_use_cases": [
            "Calling a reusable 'email processing' workflow from multiple parent workflows",
            "Orchestrating complex multi-stage pipelines",
            "Modular workflow design with shared sub-workflows",
        ],
    },
    "setStateNode": {
        "category": "Processing",
        "description": "Sets or updates values in the workflow's session state. Allows storing computed values for use by downstream nodes.",
        "when_to_use": "When you need to persist a value in the session state so other nodes can access it later via {{session.key}}.",
        "example_use_cases": [
            "Storing a user's selected preference for later use",
            "Setting a flag that downstream routers check",
            "Accumulating data across multiple iterations",
        ],
    },
    "apiToolNode": {
        "category": "Integration",
        "description": "Makes HTTP API calls (GET, POST, PUT, DELETE) to external endpoints. Returns the API response for downstream processing.",
        "when_to_use": "When the workflow needs to call a REST API endpoint (internal or external) and process the response.",
        "example_use_cases": [
            "Fetching customer data from a CRM API",
            "Sending a webhook notification",
            "Calling a third-party service for data enrichment",
        ],
    },
    "openApiNode": {
        "category": "Integration",
        "description": "Executes API calls based on an OpenAPI specification file. Uses an LLM to interpret the query and select the correct API endpoint/parameters from the spec.",
        "when_to_use": "When you have an OpenAPI/Swagger spec and want the AI to intelligently select and call the right endpoint based on natural language.",
        "example_use_cases": [
            "Querying a complex API by describing what you need in plain English",
            "Auto-generating API calls from user requests using an OpenAPI spec",
            "Exploring and using documented API endpoints without manual configuration",
        ],
    },
    "toolBuilderNode": {
        "category": "Processing",
        "description": "Wraps a sub-flow (chain of nodes) as a tool that an agentNode can call. Connects to agentNode via the tools port (output_tool -> input_tools). The sub-flow starts from starter_processor and returns results back to the agent.",
        "when_to_use": "When you want to give an agentNode access to a tool that executes a sequence of nodes (e.g., KB lookup, API call, Python code).",
        "example_use_cases": [
            "Wrapping a knowledgeBaseNode as a tool for an agent",
            "Creating a 'search database' tool using sqlNode",
            "Building a custom API-calling tool for an agent",
        ],
    },
    "pythonCodeNode": {
        "category": "Processing",
        "description": "Executes custom Python code. Input values are available via params.get('field_name'). Returns the result of the code execution.",
        "when_to_use": "When you need custom data processing, transformation, or logic that isn't covered by other node types.",
        "example_use_cases": [
            "Parsing and transforming API response data",
            "Running calculations or data analysis",
            "Custom string processing or formatting",
        ],
    },
    "dataMapperNode": {
        "category": "Processing",
        "description": "Transforms data from one structure to another using a Python script. Similar to pythonCodeNode but semantically focused on data transformation.",
        "when_to_use": "When you need to reshape, map, or transform data between nodes (e.g., converting API response format to match the next node's expected input).",
        "example_use_cases": [
            "Mapping API response fields to a different schema",
            "Extracting specific fields from a complex JSON response",
            "Converting data formats between integrations",
        ],
    },
    "knowledgeBaseNode": {
        "category": "Knowledge",
        "description": "Queries one or more Knowledge Bases using RAG (Retrieval Augmented Generation). Searches indexed documents and returns relevant chunks.",
        "when_to_use": "When the workflow needs to retrieve information from uploaded documents, FAQs, or indexed content.",
        "example_use_cases": [
            "Looking up product documentation to answer customer questions",
            "Searching through company policies for HR queries",
            "Retrieving relevant context from a knowledge base before generating a response",
        ],
    },
    "threadRAGNode": {
        "category": "Knowledge",
        "description": "Performs RAG (Retrieval Augmented Generation) over the current conversation thread. Can index messages and retrieve relevant past messages.",
        "when_to_use": "When you need to search through conversation history to find relevant context, especially in long conversations.",
        "example_use_cases": [
            "Finding relevant past messages in a long support conversation",
            "Retrieving context from earlier in a multi-turn dialogue",
            "Building conversation-aware responses using historical context",
        ],
    },
    "slackMessageNode": {
        "category": "Integration",
        "description": "Sends a message to a Slack channel. Requires Slack integration configuration (app_settings_id).",
        "when_to_use": "When the workflow needs to send notifications or messages to a Slack channel.",
        "example_use_cases": [
            "Notifying a team channel about a new support ticket",
            "Sending workflow completion alerts",
            "Posting AI-generated summaries to a Slack channel",
        ],
    },
    "gmailNode": {
        "category": "Integration",
        "description": "Sends emails via Gmail. Requires Gmail data source configuration (dataSourceId).",
        "when_to_use": "When the workflow needs to send emails (to, cc, bcc, subject, body).",
        "example_use_cases": [
            "Sending automated response emails to customers",
            "Forwarding processed information via email",
            "Sending notification emails after workflow completion",
        ],
    },
    "readMailsNode": {
        "category": "Integration",
        "description": "Reads emails from Gmail with search filters (from, to, subject, label, date range, attachments, unread). Requires Gmail data source configuration.",
        "when_to_use": "When the workflow needs to fetch and process incoming emails based on search criteria.",
        "example_use_cases": [
            "Reading unread customer emails for automated processing",
            "Fetching emails with specific labels for classification",
            "Monitoring an inbox for emails matching certain criteria",
        ],
    },
    "whatsappToolNode": {
        "category": "Integration",
        "description": "Sends a WhatsApp message to a specified recipient. Requires WhatsApp integration configuration (app_settings_id).",
        "when_to_use": "When the workflow needs to send WhatsApp messages.",
        "example_use_cases": [
            "Sending order confirmation via WhatsApp",
            "Notifying customers about ticket updates",
            "Automated WhatsApp outreach",
        ],
    },
    "zendeskTicketNode": {
        "category": "Integration",
        "description": "Creates a support ticket in Zendesk with subject, description, requester info, and tags. Requires Zendesk integration configuration (app_settings_id).",
        "when_to_use": "When the workflow needs to create support tickets in Zendesk.",
        "example_use_cases": [
            "Automatically creating tickets from customer chat messages",
            "Escalating issues detected by AI to Zendesk",
            "Creating tickets with AI-extracted metadata and tags",
        ],
    },
    "calendarEventNode": {
        "category": "Integration",
        "description": "Creates or reads calendar events via Google Calendar integration. Supports creating events and searching existing ones.",
        "when_to_use": "When the workflow needs to interact with Google Calendar (create events, check availability, read events).",
        "example_use_cases": [
            "Scheduling meetings based on AI conversation",
            "Creating follow-up calendar reminders",
            "Checking calendar availability before booking",
        ],
    },
    "jiraNode": {
        "category": "Integration",
        "description": "Creates tasks/issues in Jira. Requires Jira configuration (app_settings_id) and a space key.",
        "when_to_use": "When the workflow needs to create Jira issues or tasks.",
        "example_use_cases": [
            "Creating bug reports from customer feedback",
            "Generating task tickets from AI analysis",
            "Escalating urgent issues to Jira boards",
        ],
    },
    "sqlNode": {
        "category": "Integration",
        "description": "Executes SQL queries against a configured database. Supports two modes: manual SQL query or AI-generated SQL from natural language (using an LLM).",
        "when_to_use": "When the workflow needs to query or manipulate data in a SQL database.",
        "example_use_cases": [
            "Querying customer data from a database",
            "Running analytics queries and returning results",
            "Natural language to SQL for database exploration",
        ],
    },
    "mcpNode": {
        "category": "Integration",
        "description": "Connects to an MCP (Model Context Protocol) server, enabling the workflow to use external tools and resources via the MCP standard.",
        "when_to_use": "When you want to integrate with MCP-compatible tools and services.",
        "example_use_cases": [
            "Connecting to external tool servers via MCP",
            "Using MCP-provided resources in the workflow",
            "Integrating with custom MCP servers",
        ],
    },
    "mlModelInferenceNode": {
        "category": "ML",
        "description": "Runs inference on a trained ML model. Select a previously trained model and pass input data for predictions.",
        "when_to_use": "When you need to get predictions from a custom-trained ML model within the workflow.",
        "example_use_cases": [
            "Predicting customer churn from user data",
            "Running sentiment analysis on text",
            "Making product recommendations based on features",
        ],
    },
    "trainDataSourceNode": {
        "category": "ML",
        "description": "Loads training data from a configured data source (CSV file, database query, etc.) for ML model training pipelines.",
        "when_to_use": "When setting up an ML training pipeline and you need to load the training dataset.",
        "example_use_cases": [
            "Loading a CSV dataset for model training",
            "Querying a database for training data",
            "Fetching data from a data source for preprocessing",
        ],
    },
    "preprocessingNode": {
        "category": "ML",
        "description": "Preprocesses data for ML model training. Applies transformations using custom Python code on the loaded dataset.",
        "when_to_use": "When training data needs cleaning, transformation, or feature engineering before model training.",
        "example_use_cases": [
            "Cleaning and normalizing training data",
            "Feature engineering before model training",
            "Handling missing values and outliers",
        ],
    },
    "trainModelNode": {
        "category": "ML",
        "description": "Trains an ML model on preprocessed data. Configure model type, target column, feature columns, and validation split.",
        "when_to_use": "When you need to train a custom ML model within the platform.",
        "example_use_cases": [
            "Training a classification model on labeled data",
            "Building a regression model for price prediction",
            "Creating a custom NLP model for text classification",
        ],
    },
}


def generate_node_specs() -> str:
    """Generate the full node_specs.md content."""
    lines: list[str] = []

    lines.append("# GenAssist Workflow Node Specifications")
    lines.append("")
    lines.append("This document describes every node type available in GenAssist workflows.")
    lines.append("Use this reference to understand what each node does, when to use it,")
    lines.append("how to configure it, and how it connects to other nodes.")
    lines.append("")

    # ── Connection Rules ──────────────────────────────────────────────────
    lines.append("## Connection Rules")
    lines.append("")
    lines.append("Every node has **handlers** (ports) that define how it connects:")
    lines.append("- **target** (input) handlers: receive data from upstream nodes")
    lines.append("- **source** (output) handlers: send data to downstream nodes")
    lines.append("")
    lines.append("Handlers have a **compatibility** type:")
    lines.append("- `any`: can connect to `any` or `text` ports")
    lines.append("- `text`: can connect to `any` or `text` ports")
    lines.append("- `tools`: can ONLY connect to other `tools` ports")
    lines.append("  - Used for: toolBuilderNode.output_tool -> agentNode.input_tools")
    lines.append("")

    # ── Common Patterns ───────────────────────────────────────────────────
    lines.append("## Common Workflow Patterns")
    lines.append("")
    lines.append("### Simple Chatbot")
    lines.append("chatInputNode -> agentNode -> chatOutputNode")
    lines.append("")
    lines.append("### Chatbot with Knowledge Base")
    lines.append("chatInputNode -> agentNode -> chatOutputNode")
    lines.append("toolBuilderNode -> knowledgeBaseNode (tool for agent)")
    lines.append("toolBuilderNode.output_tool -> agentNode.input_tools")
    lines.append("")
    lines.append("### Chatbot with Multiple Tools")
    lines.append("chatInputNode -> agentNode -> templateNode -> chatOutputNode")
    lines.append("toolBuilderNode 'KB' -> knowledgeBaseNode (tool)")
    lines.append("toolBuilderNode 'API' -> apiToolNode (tool)")
    lines.append("Both toolBuilderNodes connect output_tool -> agentNode.input_tools")
    lines.append("")
    lines.append("### Branching Workflow")
    lines.append("chatInputNode -> agentNode -> routerNode")
    lines.append("routerNode.output_true -> [urgent path] -> chatOutputNode")
    lines.append("routerNode.output_false -> [normal path] -> chatOutputNode")
    lines.append("")
    lines.append("### AI Pipeline (no agent)")
    lines.append("chatInputNode -> templateNode -> llmModelNode -> templateNode -> chatOutputNode")
    lines.append("")
    lines.append("### ML Training Pipeline")
    lines.append("trainDataSourceNode -> preprocessingNode -> trainModelNode")
    lines.append("")

    # ── Node Reference ────────────────────────────────────────────────────
    # Group by category
    categories_order = [
        "I/O",
        "AI",
        "Processing",
        "Control Flow",
        "Knowledge",
        "Integration",
        "ML",
    ]
    nodes_by_category: dict[str, list[str]] = {cat: [] for cat in categories_order}

    for node_type in NODE_TYPE_LABELS:
        meta = NODE_DESCRIPTIONS.get(node_type)
        if meta:
            cat = meta["category"]
            if cat not in nodes_by_category:
                nodes_by_category[cat] = []
            nodes_by_category[cat].append(node_type)
        else:
            nodes_by_category.setdefault("Other", []).append(node_type)

    lines.append("---")
    lines.append("")
    lines.append("## Node Reference")
    lines.append("")

    for category in categories_order:
        node_types = nodes_by_category.get(category, [])
        if not node_types:
            continue

        lines.append(f"### {category} Nodes")
        lines.append("")

        for node_type in node_types:
            label = NODE_TYPE_LABELS.get(node_type, node_type)
            meta = NODE_DESCRIPTIONS.get(node_type, {})
            handlers = NODE_HANDLERS_SCHEMAS.get(node_type, [])
            fields = NODE_DIALOG_SCHEMAS.get(node_type, [])

            lines.append(f"#### {node_type} - {label}")
            lines.append(f"**Category:** {meta.get('category', 'Unknown')}")
            lines.append(f"**Description:** {meta.get('description', 'No description available.')}")
            lines.append(f"**When to use:** {meta.get('when_to_use', '')}")
            lines.append("")

            # Example use cases
            use_cases = meta.get("example_use_cases", [])
            if use_cases:
                lines.append("**Example use cases:**")
                for uc in use_cases:
                    lines.append(f"- {uc}")
                lines.append("")

            # Handlers
            if handlers:
                lines.append("**Handlers (ports):**")
                for h in handlers:
                    h_id = h.get("id", "?")
                    h_type = h.get("type", "?")
                    h_pos = h.get("position", "?")
                    h_compat = h.get("compatibility", "any")
                    lines.append(f"- `{h_id}` ({h_type}, {h_pos}, compatibility: {h_compat})")
                lines.append("")

            # Configuration fields
            if fields:
                required_fields = [f for f in fields if f.required]
                optional_fields = [f for f in fields if not f.required]

                if required_fields:
                    lines.append("**Required configuration:**")
                    for f in required_fields:
                        default_str = f" (default: {f.default})" if f.default is not None else ""
                        desc_str = f" -- {f.description}" if f.description else ""
                        options_str = ""
                        if f.options:
                            opt_values = [o.get("value", o.get("label", "?")) for o in f.options]
                            options_str = f" Options: {', '.join(opt_values)}"
                        lines.append(f"- `{f.name}` ({f.type}): {f.label}{default_str}{desc_str}{options_str}")
                    lines.append("")

                if optional_fields:
                    lines.append("**Optional configuration:**")
                    for f in optional_fields:
                        default_str = f" (default: {f.default})" if f.default is not None else ""
                        desc_str = f" -- {f.description}" if f.description else ""
                        cond_str = ""
                        if f.conditional:
                            cond_str = f" [shown when {f.conditional.field}={f.conditional.value}]"
                        lines.append(f"- `{f.name}` ({f.type}): {f.label}{default_str}{desc_str}{cond_str}")
                    lines.append("")
            else:
                lines.append("**Configuration:** No configuration fields (auto-configured).")
                lines.append("")

            lines.append("---")
            lines.append("")

    # ── Output Format ─────────────────────────────────────────────────────
    lines.append("## Workflow JSON Output Format")
    lines.append("")
    lines.append("When creating a workflow, produce a JSON object with this structure:")
    lines.append("")
    lines.append("```json")
    lines.append("""{
  "workflow": [
    {
      "uniqueId": "1",
      "node_name": "chatInputNode",
      "function_of_node": "Chat Input"
    },
    {
      "uniqueId": "2",
      "node_name": "agentNode",
      "function_of_node": "Support Agent",
      "config": {
        "systemPrompt": "You are a helpful assistant...",
        "userPrompt": "{{source.message}}",
        "type": "ToolSelector",
        "memory": true,
        "maxIterations": 5
      }
    },
    {
      "uniqueId": "3",
      "node_name": "chatOutputNode",
      "function_of_node": "Chat Output"
    }
  ],
  "edges": [
    { "from": "1", "to": "2" },
    { "from": "2", "to": "3" },
    { "from": "4", "to": "2", "sourceHandle": "output_tool", "targetHandle": "input_tools" }
  ]
}""")
    lines.append("```")
    lines.append("")
    lines.append("**Rules:**")
    lines.append("- `uniqueId`: simple string identifier (e.g., \"1\", \"2\", \"3\")")
    lines.append("- `node_name`: must be one of the node type keys listed above")
    lines.append("- `function_of_node`: human-readable name/purpose")
    lines.append("- `config` (optional): override default configuration values")
    lines.append("- `edges.from`/`edges.to`: reference uniqueId values")
    lines.append("- `edges.sourceHandle` defaults to \"output\", `edges.targetHandle` defaults to \"input\"")
    lines.append("- For tool connections: sourceHandle=\"output_tool\", targetHandle=\"input_tools\"")
    lines.append("- For router branches: sourceHandle=\"output_true\" or \"output_false\"")
    lines.append("")

    return "\n".join(lines)


def main():
    content = generate_node_specs()
    output_path = Path(__file__).parent / "node_specs.md"
    output_path.write_text(content, encoding="utf-8")
    print(f"Generated {output_path} ({len(content)} bytes)")


if __name__ == "__main__":
    main()
