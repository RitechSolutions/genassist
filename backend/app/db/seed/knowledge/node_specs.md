# GenAssist Workflow Node Specifications

This document describes every node type available in GenAssist workflows.
Use this reference to understand what each node does, when to use it,
how to configure it, and how it connects to other nodes.

## Connection Rules

Every node has **handlers** (ports) that define how it connects:
- **target** (input) handlers: receive data from upstream nodes
- **source** (output) handlers: send data to downstream nodes

Handlers have a **compatibility** type:
- `any`: can connect to `any` or `text` ports
- `text`: can connect to `any` or `text` ports
- `tools`: can ONLY connect to other `tools` ports
  - Used for: toolBuilderNode.output_tool -> agentNode.input_tools

## Common Workflow Patterns

### Simple Chatbot
chatInputNode -> agentNode -> chatOutputNode

### Chatbot with Knowledge Base
chatInputNode -> agentNode -> chatOutputNode
toolBuilderNode -> knowledgeBaseNode (tool for agent)
toolBuilderNode.output_tool -> agentNode.input_tools

### Chatbot with Multiple Tools
chatInputNode -> agentNode -> templateNode -> chatOutputNode
toolBuilderNode 'KB' -> knowledgeBaseNode (tool)
toolBuilderNode 'API' -> apiToolNode (tool)
Both toolBuilderNodes connect output_tool -> agentNode.input_tools

### Branching Workflow
chatInputNode -> agentNode -> routerNode
routerNode.output_true -> [urgent path] -> chatOutputNode
routerNode.output_false -> [normal path] -> chatOutputNode

### AI Pipeline (no agent)
chatInputNode -> templateNode -> llmModelNode -> templateNode -> chatOutputNode

### ML Training Pipeline
trainDataSourceNode -> preprocessingNode -> trainModelNode

---

## Node Reference

### I/O Nodes

#### chatInputNode - Chat Input
**Category:** I/O
**Description:** Entry point for chat-based workflows. Receives the user's message and passes it downstream.
**When to use:** Every chat-based workflow MUST start with this node. It captures the user's input.

**Example use cases:**
- Starting point for a customer support chatbot
- Receiving user queries in a Q&A assistant
- Capturing commands for an automation workflow triggered by chat

**Handlers (ports):**
- `output` (source, right, compatibility: any)

**Configuration:** No configuration fields (auto-configured).

---

#### chatOutputNode - Chat Output
**Category:** I/O
**Description:** Exit point for chat-based workflows. Sends the final response back to the user.
**When to use:** Every chat-based workflow MUST end with this node. It delivers the result to the user.

**Example use cases:**
- Returning the agent's final answer to the user
- Displaying formatted results after data processing
- Sending confirmation messages after an action is completed

**Handlers (ports):**
- `input` (target, left, compatibility: any)

**Configuration:** No configuration fields (auto-configured).

---

### AI Nodes

#### agentNode - Agent
**Category:** AI
**Description:** An LLM-powered agent that can reason, use tools, and hold multi-turn conversations. Supports ReAct, ToolSelector, SimpleToolExecutor, and ChainOfThought patterns.
**When to use:** When you need AI reasoning, tool calling, or conversational ability. This is the core 'brain' of most workflows.

**Example use cases:**
- Customer support chatbot with tool access
- Data analysis assistant that queries databases via tools
- Email classifier that routes to different actions

**Handlers (ports):**
- `input` (target, left, compatibility: any)
- `input_tools` (target, bottom, compatibility: tools)
- `output` (source, right, compatibility: any)

**Required configuration:**
- `providerId` (select): LLM Provider -- select the AI model to use
- `systemPrompt` (text): System Prompt (default: "You are a helpful assistant that helps the user with their requests.")
- `userPrompt` (text): User Prompt (default: "{{session.message}}")
- `type` (select): Agent Type (default: "ToolSelection") -- Options: ReAct, ToolSelector, SimpleToolExecutor, ChainOfThought
- `maxIterations` (number): Max Iterations (default: 3) -- max reasoning cycles
- `memory` (boolean): Enable Memory

**Optional configuration:**
- `name` (text): Node Name
- `memoryTrimmingMode` (select): Memory Trimming Mode (default: message_count) -- How to limit conversation history. Options: message_count, token_budget, message_compacting, rag_retrieval
- `maxMessages` (number): Max Messages (default: 10) [shown when memoryTrimmingMode=message_count]
- `compactingThreshold` (number): Compacting Threshold (default: 20) [shown when memoryTrimmingMode=message_compacting]
- `compactingKeepRecent` (number): Recent Messages to Keep (default: 10) [shown when memoryTrimmingMode=message_compacting]
- `compactingModel` (select): Compacting Model [shown when memoryTrimmingMode=message_compacting]
- `compactingImportantEntities` (tags): Important Entities to Preserve [shown when memoryTrimmingMode=message_compacting]
- `tokenBudget` (number): Total Token Budget (default: 10000) [shown when memoryTrimmingMode=token_budget]
- `conversationHistoryTokens` (number): Conversation History Allocation (default: 5000) [shown when memoryTrimmingMode=token_budget]
- RAG retrieval settings (ragPassthroughThreshold, ragGroupSize, ragGroupOverlap, ragQueryContextMessages, ragTopK, ragRecentMessages, ragMaxHistoryHours) [shown when memoryTrimmingMode=rag_retrieval]

---

#### llmModelNode - LLM Model
**Category:** AI
**Description:** A standalone LLM call node. Sends a system prompt + user prompt to a language model and returns the response. Similar to agentNode but without tool calling or ReAct loops.
**When to use:** When you need a simple LLM completion without agent behavior (no tools, no reasoning loops). Good for text generation, summarization, classification.

**Example use cases:**
- Summarizing a document or email
- Classifying text into categories
- Generating a response from a template-filled prompt

**Handlers (ports):**
- `input` (target, left, compatibility: any)
- `output` (source, right, compatibility: any)

**Required configuration:**
- `providerId` (select): LLM Provider
- `systemPrompt` (text): System Prompt
- `userPrompt` (text): User Prompt
- `type` (select): Type
- `memory` (boolean): Enable Memory

**Optional configuration:**
- `name` (text): Node Name
- `memoryTrimmingMode` (select): Memory Trimming Mode (default: message_count)
- Memory sub-settings same as agentNode (conditional on memoryTrimmingMode)

---

### Processing Nodes

#### templateNode - Template
**Category:** Processing
**Description:** Formats text using a template with variable substitution. Variables use {{source.field}} or {{session.field}} syntax.
**When to use:** When you need to format or combine data from previous nodes into a specific text format before passing it downstream.

**Example use cases:**
- Formatting agent output before sending to chatOutputNode
- Building a structured prompt from multiple data sources
- Composing an email body from extracted data fields

**Handlers (ports):**
- `input` (target, left, compatibility: any)
- `output` (source, right, compatibility: any)

**Required configuration:**
- `template` (text): Template -- the text template with {{variable}} placeholders

**Optional configuration:**
- `name` (text): Node Name

---

#### toolBuilderNode - Tool Builder
**Category:** Processing
**Description:** Wraps a sub-flow (chain of nodes) as a tool that an agentNode can call. Connects to agentNode via the tools port (output_tool -> input_tools). The sub-flow starts from starter_processor and returns results back to the agent.
**When to use:** When you want to give an agentNode access to a tool that executes a sequence of nodes (e.g., KB lookup, API call, Python code).

**Example use cases:**
- Wrapping a knowledgeBaseNode as a tool for an agent
- Creating a 'search database' tool using sqlNode
- Building a custom API-calling tool for an agent

**Handlers (ports):**
- `output_tool` (source, top, compatibility: tools) -- connect to agentNode.input_tools
- `starter_processor` (source, bottom, compatibility: any) -- connect to the first node of the tool's sub-flow
- `end_processor` (target, bottom, compatibility: any) -- receives the sub-flow's final output

**Required configuration:**
- `description` (text): Description -- describes what this tool does (the agent sees this to decide when to use it)
- `forwardTemplate` (boolean): Return data directly as agent output (default: "{}")

**Optional configuration:**
- `name` (text): Node Name

---

#### pythonCodeNode - Python Code
**Category:** Processing
**Description:** Executes custom Python code. Input values are available via params.get('field_name'). Returns the result of the code execution.
**When to use:** When you need custom data processing, transformation, or logic that isn't covered by other node types.

**Example use cases:**
- Parsing and transforming API response data
- Running calculations or data analysis
- Custom string processing or formatting

**Handlers (ports):**
- `input` (target, left, compatibility: any)
- `output` (source, right, compatibility: any)

**Required configuration:**
- `code` (text): Python Code -- the Python code to execute

**Optional configuration:**
- `name` (text): Node Name

---

#### dataMapperNode - Data Mapper
**Category:** Processing
**Description:** Transforms data from one structure to another using a Python script. Similar to pythonCodeNode but semantically focused on data transformation.
**When to use:** When you need to reshape, map, or transform data between nodes.

**Example use cases:**
- Mapping API response fields to a different schema
- Extracting specific fields from a complex JSON response
- Converting data formats between integrations

**Handlers (ports):**
- `input` (target, left, compatibility: any)
- `output` (source, right, compatibility: any)

**Required configuration:**
- `pythonScript` (text): Python Script

**Optional configuration:**
- `name` (text): Node Name

---

#### setStateNode - Set State
**Category:** Processing
**Description:** Sets or updates values in the workflow's session state. Allows storing computed values for use by downstream nodes.
**When to use:** When you need to persist a value in the session state so other nodes can access it later via {{session.key}}.

**Example use cases:**
- Storing a user's selected preference for later use
- Setting a flag that downstream routers check
- Accumulating data across multiple iterations

**Handlers (ports):**
- `input` (target, left, compatibility: any)
- `output` (source, right, compatibility: any)

**Configuration:** Configured via the workflow studio UI (key-value state assignments).

---

### Control Flow Nodes

#### routerNode - Router
**Category:** Control Flow
**Description:** Conditional branching node. Compares two values and routes to output_true or output_false. Supports conditions: equals, not_equals, contains, greater_than, less_than, etc.
**When to use:** When the workflow needs to branch based on a condition.

**Example use cases:**
- Routing high-priority tickets to Jira, low-priority to Slack
- Branching based on email sender domain
- Conditional processing based on classification results

**Handlers (ports):**
- `input` (target, left, compatibility: any)
- `output_true` (source, right, compatibility: any) -- taken when condition is true
- `output_false` (source, right, compatibility: any) -- taken when condition is false

**Required configuration:**
- `first_value` (text): First Value -- left side of comparison (can use {{source.field}})
- `compare_condition` (select): Compare Condition -- equals, not_equals, contains, greater_than, less_than, etc.
- `second_value` (text): Second Value -- right side of comparison

**Optional configuration:**
- `name` (text): Node Name

---

#### aggregatorNode - Aggregator
**Category:** Control Flow
**Description:** Collects outputs from multiple upstream nodes and combines them using a strategy (list, merge, first, last).
**When to use:** When multiple parallel branches need to be combined back into a single flow.

**Example use cases:**
- Merging results from parallel API calls
- Collecting outputs from multiple tool executions
- Reconverging after a router's true/false branches

**Handlers (ports):**
- `input` (target, left, compatibility: any)
- `output` (source, right, compatibility: any)

**Required configuration:**
- `aggregationStrategy` (select): Aggregation Strategy -- list, merge, first, last
- `timeoutSeconds` (number): Timeout (seconds)

**Optional configuration:**
- `name` (text): Node Name
- `forwardTemplate` (text): Forward Template
- `requireAllInputs` (boolean): Require All Inputs

---

#### humanInTheLoopNode - Human in the Loop
**Category:** Control Flow
**Description:** Pauses workflow execution and presents a form to the user for input. Resumes after the user submits.
**When to use:** When a human needs to review, approve, or provide additional input before the workflow continues.

**Example use cases:**
- Manager approval before creating a Jira ticket
- User confirmation before sending an email
- Human review of AI-generated content before publishing

**Handlers (ports):**
- `input` (target, left, compatibility: any)
- `output` (source, right, compatibility: any)

**Configuration:** Form fields configured via the workflow studio UI.

---

#### workflowExecutorNode - Workflow Executor
**Category:** Control Flow
**Description:** Executes another workflow as a sub-workflow. Enables workflow composition and reuse.
**When to use:** When you want to call another existing workflow as a building block within a larger workflow.

**Example use cases:**
- Calling a reusable 'email processing' workflow from multiple parent workflows
- Orchestrating complex multi-stage pipelines
- Modular workflow design with shared sub-workflows

**Handlers (ports):**
- `input` (target, left, compatibility: any)
- `output` (source, right, compatibility: any)

**Configuration:** Select the target workflow to execute.

---

### Knowledge Nodes

#### knowledgeBaseNode - Knowledge Base
**Category:** Knowledge
**Description:** Queries one or more Knowledge Bases using RAG (Retrieval Augmented Generation). Searches indexed documents and returns relevant chunks.
**When to use:** When the workflow needs to retrieve information from uploaded documents, FAQs, or indexed content.

**Example use cases:**
- Looking up product documentation to answer customer questions
- Searching through company policies for HR queries
- Retrieving relevant context from a knowledge base before generating a response

**Handlers (ports):**
- `input` (target, left, compatibility: any)
- `output` (source, right, compatibility: any)

**Required configuration:**
- `query` (text): Query -- the search query (can use {{session.message}})
- `limit` (number): Limit -- max results to return
- `force` (boolean): Force Limit
- `selectedBases` (tags): Knowledge Bases -- which KB(s) to search

**Optional configuration:**
- `name` (text): Node Name

---

#### threadRAGNode - Thread RAG
**Category:** Knowledge
**Description:** Performs RAG over the current conversation thread. Can index messages and retrieve relevant past messages.
**When to use:** When you need to search through conversation history to find relevant context.

**Example use cases:**
- Finding relevant past messages in a long support conversation
- Retrieving context from earlier in a multi-turn dialogue
- Building conversation-aware responses using historical context

**Handlers (ports):**
- `input` (target, left, compatibility: any)
- `output` (source, right, compatibility: any)

**Required configuration:**
- `action` (select): Action

**Optional configuration:**
- `name` (text): Node Name
- `query` (text): Query
- `top_k` (number): Top K
- `message` (text): Message

---

### Integration Nodes

#### apiToolNode - API Tool
**Category:** Integration
**Description:** Makes HTTP API calls (GET, POST, PUT, DELETE) to external endpoints.
**When to use:** When the workflow needs to call a REST API endpoint.

**Example use cases:**
- Fetching customer data from a CRM API
- Sending a webhook notification
- Calling a third-party service for data enrichment

**Handlers (ports):**
- `input` (target, left, compatibility: any)
- `output` (source, right, compatibility: any)

**Required configuration:**
- `endpoint` (text): Endpoint URL (default: "http://localhost/api/endpoint")
- `method` (select): HTTP Method (default: "GET")

**Optional configuration:**
- `name` (text): Node Name
- `requestBody` (text): Request Body (JSON)

---

#### openApiNode - Open API
**Category:** Integration
**Description:** Executes API calls based on an OpenAPI specification file. Uses an LLM to interpret the query and select the correct endpoint.
**When to use:** When you have an OpenAPI/Swagger spec and want AI-assisted API calling.

**Example use cases:**
- Querying a complex API by describing what you need in plain English
- Auto-generating API calls from user requests
- Exploring documented API endpoints without manual configuration

**Handlers (ports):**
- `input` (target, left, compatibility: any)
- `output` (source, right, compatibility: any)

**Required configuration:**
- `providerId` (select): LLM Provider
- `originalFileName` (text): Specification File
- `query` (text): Query

**Optional configuration:**
- `name` (text): Node Name

---

#### slackMessageNode - Slack Message
**Category:** Integration
**Description:** Sends a message to a Slack channel. Requires Slack integration configuration.
**When to use:** When the workflow needs to send notifications or messages to Slack.

**Example use cases:**
- Notifying a team channel about a new support ticket
- Sending workflow completion alerts
- Posting AI-generated summaries to Slack

**Handlers (ports):**
- `input` (target, left, compatibility: any)
- `output` (source, right, compatibility: any)

**Required configuration:**
- `app_settings_id` (select): Configuration Vars -- Slack integration settings
- `channel` (text): Channel ID
- `message` (text): Message

**Optional configuration:**
- `name` (text): Node Name

---

#### gmailNode - Gmail
**Category:** Integration
**Description:** Sends emails via Gmail. Requires Gmail data source configuration.
**When to use:** When the workflow needs to send emails.

**Example use cases:**
- Sending automated response emails to customers
- Forwarding processed information via email
- Sending notification emails after workflow completion

**Handlers (ports):**
- `input` (target, left, compatibility: any)

**Required configuration:**
- `dataSourceId` (select): Connector -- Gmail data source
- `operation` (select): Operation
- `to` (text): To
- `subject` (text): Subject
- `body` (text): Body

**Optional configuration:**
- `name` (text): Node Name
- `cc` (text): CC
- `bcc` (text): BCC

---

#### readMailsNode - Read Mails
**Category:** Integration
**Description:** Reads emails from Gmail with search filters. Requires Gmail data source configuration.
**When to use:** When the workflow needs to fetch and process incoming emails.

**Example use cases:**
- Reading unread customer emails for automated processing
- Fetching emails with specific labels for classification
- Monitoring an inbox for emails matching criteria

**Handlers (ports):**
- `input` (target, left, compatibility: any)
- `output` (source, right, compatibility: any)

**Required configuration:**
- `dataSourceId` (select): Gmail Data Source

**Optional configuration:**
- `name` (text): Node Name
- `searchCriteria.from` (text): From Email
- `searchCriteria.to` (text): To Email
- `searchCriteria.subject` (text): Subject Contains
- `searchCriteria.label` (select): Gmail Label
- `searchCriteria.newer_than` (select): Newer Than
- `searchCriteria.older_than` (select): Older Than
- `searchCriteria.max_results` (number): Max Results
- `searchCriteria.has_attachment` (boolean): Has Attachment
- `searchCriteria.is_unread` (boolean): Unread Only
- `searchCriteria.custom_query` (text): Custom Gmail Query

---

#### whatsappToolNode - WhatsApp
**Category:** Integration
**Description:** Sends a WhatsApp message to a specified recipient. Requires WhatsApp integration configuration.
**When to use:** When the workflow needs to send WhatsApp messages.

**Example use cases:**
- Sending order confirmation via WhatsApp
- Notifying customers about ticket updates
- Automated WhatsApp outreach

**Handlers (ports):**
- `input` (target, left, compatibility: any)

**Required configuration:**
- `app_settings_id` (select): Configuration Vars -- WhatsApp integration settings
- `recipient_number` (text): Recipient Number
- `message` (text): Message

**Optional configuration:**
- `name` (text): Node Name

---

#### zendeskTicketNode - Zendesk Ticket
**Category:** Integration
**Description:** Creates a support ticket in Zendesk. Requires Zendesk integration configuration.
**When to use:** When the workflow needs to create support tickets in Zendesk.

**Example use cases:**
- Automatically creating tickets from customer chat messages
- Escalating issues detected by AI to Zendesk
- Creating tickets with AI-extracted metadata and tags

**Handlers (ports):**
- `input` (target, left, compatibility: text)

**Required configuration:**
- `app_settings_id` (select): Configuration Vars -- Zendesk integration settings
- `subject` (text): Subject
- `description` (text): Description
- `requester_name` (text): Requester Name
- `requester_email` (text): Requester Email

**Optional configuration:**
- `name` (text): Node Name
- `tags` (tags): Tags

---

#### calendarEventNode - Calendar Event
**Category:** Integration
**Description:** Creates or reads calendar events via Google Calendar integration.
**When to use:** When the workflow needs to interact with Google Calendar.

**Example use cases:**
- Scheduling meetings based on AI conversation
- Creating follow-up calendar reminders
- Checking calendar availability

**Handlers (ports):**
- `input` (target, left, compatibility: any)
- `output` (source, right, compatibility: any)

**Required configuration:**
- `dataSourceId` (select): Connector -- Calendar data source
- `summary` (text): Summary
- `operation` (select): Operation

**Optional configuration:**
- `name` (text): Node Name
- `start` (text): Start Time
- `end` (text): End Time
- `subjectContains` (text): Subject Contains

---

#### jiraNode - Jira
**Category:** Integration
**Description:** Creates tasks/issues in Jira. Requires Jira configuration and a space key.
**When to use:** When the workflow needs to create Jira issues or tasks.

**Example use cases:**
- Creating bug reports from customer feedback
- Generating task tickets from AI analysis
- Escalating urgent issues to Jira boards

**Handlers (ports):**
- `input` (target, left, compatibility: any)
- `output` (source, right, compatibility: any)

**Required configuration:**
- `app_settings_id` (select): Configuration Vars -- Jira integration settings
- `spaceKey` (text): Space Key
- `taskName` (text): Task Name

**Optional configuration:**
- `name` (text): Node Name
- `taskDescription` (text): Task Description

---

#### sqlNode - SQL
**Category:** Integration
**Description:** Executes SQL queries against a configured database. Supports manual SQL or AI-generated SQL from natural language.
**When to use:** When the workflow needs to query or manipulate data in a SQL database.

**Example use cases:**
- Querying customer data from a database
- Running analytics queries and returning results
- Natural language to SQL for database exploration

**Handlers (ports):**
- `input` (target, left, compatibility: any)
- `output` (source, right, compatibility: any)

**Required configuration:**
- `dataSourceId` (select): Data Source
- `mode` (select): Mode -- Options: sqlQuery (Write SQL Manually), humanQuery (Generate SQL from Text)
- `sqlQuery` (text): SQL Query [shown when mode=sqlQuery]
- `providerId` (select): LLM Provider [shown when mode=humanQuery]
- `humanQuery` (text): Query in Plain English [shown when mode=humanQuery]

**Optional configuration:**
- `name` (text): Node Name
- `systemPrompt` (text): System Prompt [shown when mode=humanQuery]

---

#### mcpNode - MCP
**Category:** Integration
**Description:** Connects to an MCP (Model Context Protocol) server for external tools and resources.
**When to use:** When you want to integrate with MCP-compatible tools and services.

**Example use cases:**
- Connecting to external tool servers via MCP
- Using MCP-provided resources in the workflow
- Integrating with custom MCP servers

**Handlers (ports):**
- `input` (target, left, compatibility: any)
- `output` (source, right, compatibility: any)

**Configuration:** MCP server connection configured via the workflow studio UI.

---

### ML Nodes

#### mlModelInferenceNode - ML Model Inference
**Category:** ML
**Description:** Runs inference on a trained ML model. Select a previously trained model and pass input data for predictions.
**When to use:** When you need predictions from a custom-trained ML model.

**Example use cases:**
- Predicting customer churn from user data
- Running sentiment analysis on text
- Making product recommendations

**Handlers (ports):**
- `input` (target, left, compatibility: any)
- `output` (source, right, compatibility: any)

**Required configuration:**
- `modelId` (select): ML Model
- `modelName` (text): Model Name

**Optional configuration:**
- `name` (text): Node Name

---

#### trainDataSourceNode - Train Data Source
**Category:** ML
**Description:** Loads training data from a configured data source for ML model training pipelines.
**When to use:** When setting up an ML training pipeline and you need to load the training dataset.

**Example use cases:**
- Loading a CSV dataset for model training
- Querying a database for training data
- Fetching data from a data source for preprocessing

**Handlers (ports):**
- `input` (target, left, compatibility: any)
- `output` (source, right, compatibility: any)

**Required configuration:**
- `sourceType` (select): Source Type

**Optional configuration:**
- `name` (text): Node Name
- `dataSourceType` (select): Data Source Type
- `dataSourceId` (text): Data Source
- `query` (text): Query
- `csvFile` (text): CSV File

---

#### preprocessingNode - Preprocessing
**Category:** ML
**Description:** Preprocesses data for ML model training. Applies transformations using custom Python code.
**When to use:** When training data needs cleaning or feature engineering before model training.

**Example use cases:**
- Cleaning and normalizing training data
- Feature engineering before model training
- Handling missing values and outliers

**Handlers (ports):**
- `input` (target, left, compatibility: any)
- `output` (source, right, compatibility: any)

**Required configuration:**
- `fileUrl` (text): File URL

**Optional configuration:**
- `name` (text): Node Name
- `pythonCode` (text): Python Code

---

#### trainModelNode - Train Model
**Category:** ML
**Description:** Trains an ML model on preprocessed data. Configure model type, target column, feature columns, and validation split.
**When to use:** When you need to train a custom ML model within the platform.

**Example use cases:**
- Training a classification model on labeled data
- Building a regression model for price prediction
- Creating a custom NLP model for text classification

**Handlers (ports):**
- `input` (target, left, compatibility: any)
- `output` (source, right, compatibility: any)

**Required configuration:**
- `fileUrl` (text): File URL
- `modelType` (select): Model Type
- `targetColumn` (text): Target Column
- `featureColumns` (tags): Feature Columns
- `validationSplit` (number): Validation Split

**Optional configuration:**
- `name` (text): Node Name

---

## Workflow JSON Output Format

When creating a workflow, produce a JSON object with this structure:

```json
{
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
}
```

**Rules:**
- `uniqueId`: simple string identifier (e.g., "1", "2", "3")
- `node_name`: must be one of the node type keys listed above
- `function_of_node`: human-readable name/purpose
- `config` (optional): override default configuration values
- `edges.from`/`edges.to`: reference uniqueId values
- `edges.sourceHandle` defaults to "output", `edges.targetHandle` defaults to "input"
- For tool connections: sourceHandle="output_tool", targetHandle="input_tools"
- For router branches: sourceHandle="output_true" or "output_false"
