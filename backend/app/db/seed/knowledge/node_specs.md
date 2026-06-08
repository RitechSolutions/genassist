# GenAssist Workflow Node Specifications

This document is the authoritative reference for every node type available in GenAssist workflows. Use it to understand what each node does, how to configure it, and how it connects to other nodes.

---

## Connection System

Nodes connect via **handlers** (ports). Each handler has:
- **type**: `source` (output) or `target` (input)
- **position**: left, right, top, bottom
- **compatibility**: `any`, `text`, `tools`

**Compatibility rules:**
- `any` ↔ `any`: allowed
- `any` ↔ `text`: allowed
- `text` ↔ `text`: allowed
- `tools` ↔ `tools`: allowed (ONLY tools-to-tools)
- `any` / `text` → `tools`: NOT allowed

**CRITICAL — Single Input Rule:**
Most nodes accept only ONE incoming edge to their `input` handler. You CANNOT connect two nodes to the same node's input (except `aggregatorNode`, which is specifically designed to receive multiple inputs). If a workflow has branches (e.g., after a routerNode), each branch MUST have its own separate `chatOutputNode`. Do NOT merge branches into a single chatOutputNode.

**Edge format:**
```json
{"from": "nodeId1", "to": "nodeId2"}
```
Defaults: `sourceHandle = "output"`, `targetHandle = "input"`. Override for special connections:
- Tool: `sourceHandle: "output_tool"`, `targetHandle: "input_tools"`
- Tool sub-flow: `sourceHandle: "starter_processor"`, `targetHandle: "input"`
- Router true: `sourceHandle: "output_true"`
- Router false: `sourceHandle: "output_false"`

---

## Common Workflow Patterns

### Simple Chatbot
```
chatInputNode(1) → agentNode(2) → chatOutputNode(3)
Edges: 1→2, 2→3
```

### Chatbot with Knowledge Base
```
chatInputNode(1) → agentNode(2) → chatOutputNode(3)
toolBuilderNode(4) → knowledgeBaseNode(5)
Edges:
  1→2 (regular)
  2→3 (regular)
  4→2 (sourceHandle: "output_tool", targetHandle: "input_tools")
  4→5 (sourceHandle: "starter_processor", targetHandle: "input")
```

### Chatbot with Multiple Tools
```
chatInputNode(1) → agentNode(2) → chatOutputNode(3)
toolBuilderNode(4) → knowledgeBaseNode(5)
toolBuilderNode(6) → apiToolNode(7)
Edges:
  1→2, 2→3
  4→2 (output_tool → input_tools)
  4→5 (starter_processor → input)
  6→2 (output_tool → input_tools)
  6→7 (starter_processor → input)
```

### Branching Workflow
Each branch MUST have its own chatOutputNode — nodes only accept one input edge (except aggregatorNode).
```
chatInputNode(1) → routerNode(2)
  output_true → agentNode(3) → chatOutputNode(5)
  output_false → agentNode(4) → chatOutputNode(6)
Edges:
  1→2
  2→3 (sourceHandle: "output_true")
  2→4 (sourceHandle: "output_false")
  3→5
  4→6
```

### Topic-Based Routing (guardrail / topic filter)
**IMPORTANT:** routerNode can ONLY do simple string comparisons (equals, contains, etc.). It CANNOT do semantic analysis or topic classification. To route based on topic/intent, you MUST use an LLM or agent first to classify the message, then route on the classification output.

Pattern: chatInput → classifierLLM → router (checks classification) → branches
```
chatInputNode(1) → llmModelNode(2) → routerNode(3)
  output_true → agentNode(4) → chatOutputNode(6)
  output_false → templateNode(5) → chatOutputNode(7)

llmModelNode(2) config:
  systemPrompt: "Classify if the user's message is about [TOPIC]. Respond with exactly 'on_topic' or 'off_topic'."
  userPrompt: "{{source.message}}"

routerNode(3) config:
  first_value: "{{source.message}}"
  compare_condition: "contains"
  second_value: "on_topic"

Edges:
  1→2, 2→3
  3→4 (sourceHandle: "output_true")
  3→5 (sourceHandle: "output_false")
  4→6, 5→7
```

### AI Pipeline (no agent)
```
chatInputNode(1) → templateNode(2) → llmModelNode(3) → chatOutputNode(4)
Edges: 1→2, 2→3, 3→4
```

### ML Training Pipeline
```
trainDataSourceNode(1) → preprocessingNode(2) → trainModelNode(3)
Edges: 1→2, 2→3
```

---

## Architecture Rules

These rules are **non-negotiable**. Violating any of them produces a broken workflow. Always verify your workflow against these before outputting JSON.

### Connection Rules
- **Single input rule**: Every node accepts ONLY ONE incoming edge — except `aggregatorNode`. NEVER connect two edges to the same node's input.
- **Branching rule**: When a workflow branches (e.g., after a routerNode), each branch MUST have its own separate `chatOutputNode`. Do NOT merge branches into a single chatOutputNode.
- **Output formatting**: If the user wants formatted output, add a `templateNode` before `chatOutputNode` to structure the response.

### Router Rules
- `routerNode` does **SIMPLE STRING COMPARISON only**. It CANNOT understand topics, intent, meaning, or analyze content.
- NEVER use routerNode to check if a document contains a keyword, if a search returned results, or any semantic condition.
- The `agentNode` handles all semantic decisions — it reads tool results and decides what to do next based on its reasoning and systemPrompt instructions.
- routerNode is ONLY appropriate for simple deterministic routing (e.g., checking a classification label output by an llmModelNode).
- **WRONG**: `knowledgeBaseNode → routerNode` (to check if results contain something) — the agent should decide this.
- **WRONG**: `chatInput → routerNode` (to check if message is about a topic)
- **RIGHT**: `chatInput → llmModelNode` (classifies topic) → `routerNode` (checks classification string)
- If the user's use case involves "if X is found, do Y", put the search as a **TOOL** of the agent and let the agent decide via its reasoning + systemPrompt instructions. Do NOT use a routerNode for this.
- routerNode config has ONLY these fields: `first_value`, `compare_condition`, `second_value`. Do NOT invent fields like `condition`, `trueLabel`, `falseLabel`.

### Tool Connection Rules
- Integration and data nodes (`knowledgeBaseNode`, `zendeskTicketNode`, `slackMessageNode`, `gmailNode`, `jiraNode`, `apiToolNode`, `sqlNode`, `calendarEventNode`, `readMailsNode`, `whatsappToolNode`, etc.) **MUST** be connected as **TOOLS** of an `agentNode` via a `toolBuilderNode`. They must **NEVER** be placed as standalone nodes in the main chain.
- The `agentNode` decides WHEN and WHETHER to call each tool based on its reasoning. This is how the agent handles conditional logic like "if X is found, do Y" — the agent reads the tool result and decides the next action.
- Tools connect **FROM** `toolBuilderNode` **TO** `agentNode` — NOT the reverse.
- **WRONG**: `agentNode → knowledgeBaseNode → routerNode` (inline chain)
- **RIGHT**: `toolBuilderNode → agentNode` (tool connection), `toolBuilderNode → knowledgeBaseNode` (processor connection)
- Every tool requires **BOTH** edges:
  - `{"from": "<toolBuilder_id>", "to": "<agent_id>", "sourceHandle": "output_tool", "targetHandle": "input_tools"}` — registers the tool with the agent
  - `{"from": "<toolBuilder_id>", "to": "<sub_node_id>", "sourceHandle": "starter_processor", "targetHandle": "input"}` — connects the tool's processor

### Integration Rules
- Use dedicated nodes where available: `zendeskTicketNode` for Zendesk, `slackMessageNode` for Slack, `jiraNode` for Jira, `gmailNode` for Gmail, `knowledgeBaseNode` for document search, `calendarEventNode` for calendar, `readMailsNode` for reading emails, `whatsappToolNode` for WhatsApp. Only use `apiToolNode` for APIs without a dedicated node.
- **ALL** integration nodes MUST be connected as tools of an `agentNode`. NEVER place them inline in the main flow.

### Node Config Rules
- Every chat workflow MUST start with `chatInputNode` and end with `chatOutputNode`.
- Agent and LLM nodes MUST have `"userPrompt": "{{session.message}}"`. NEVER set it to null, empty, or literal text.
- Use `{{session.message}}` for tool/KB query fields.
- Write real, specific `systemPrompt` values. Never use generic placeholders like "You are a helpful assistant."

### Edge Format Reference
Regular connections — no handles needed:
```json
{"from": "1", "to": "2"}
```

Router connections — must specify branch:
```json
{"from": "<router_id>", "to": "<target>", "sourceHandle": "output_true", "targetHandle": "input"}
{"from": "<router_id>", "to": "<target>", "sourceHandle": "output_false", "targetHandle": "input"}
```

Tool connections — both edges required:
```json
{"from": "<toolBuilder_id>", "to": "<agent_id>", "sourceHandle": "output_tool", "targetHandle": "input_tools"}
{"from": "<toolBuilder_id>", "to": "<sub_node_id>", "sourceHandle": "starter_processor", "targetHandle": "input"}
```

---

## Node Reference

---

### chatInputNode — Chat Input
**Category:** I/O
**Purpose:** Entry point for chat workflows. Receives the user's message. Every chat workflow MUST start with this node.
**Use cases:** Customer support chatbot entry, Q&A assistant input, chat-triggered automation.

**Handlers:**
| ID | Type | Position | Compatibility |
|---|---|---|---|
| output | source | right | any |

**Config:** None (auto-configured).

---

### chatOutputNode — Chat Output
**Category:** I/O
**Purpose:** Exit point for chat workflows. Sends the final response to the user. Every chat workflow MUST end with this node.
**Use cases:** Returning agent answers, displaying processed results, sending confirmation messages.

**Handlers:**
| ID | Type | Position | Compatibility |
|---|---|---|---|
| input | target | left | any |

**Config:** None (auto-configured).

---

### agentNode — Agent
**Category:** AI
**Purpose:** LLM-powered agent with tool calling, reasoning loops, and conversation memory. The core "brain" of most workflows. Supports multiple agent patterns.
**Use cases:** Customer support chatbot with tools, data analysis assistant, email classifier, conversational AI with integrations.

**Handlers:**
| ID | Type | Position | Compatibility |
|---|---|---|---|
| input | target | left | any |
| input_tools | target | bottom | tools |
| output | source | right | any |

**Required config:**
| Field | Type | Default | Description |
|---|---|---|---|
| providerId | select | — | LLM provider to use |
| systemPrompt | text | "You are a helpful assistant..." | Instructions for the agent |
| userPrompt | text | "{{source.message}}" | User input template. MUST be "{{source.message}}" — never replace with literal text |
| type | select | "ToolSelector" | Agent pattern: ReActAgent, ToolSelector, SimpleToolExecutor, ReActAgentLC |
| maxIterations | number | 7 | Max reasoning cycles before stopping |
| memory | boolean | false | Enable conversation memory |

**Optional config:**
| Field | Type | Default | Condition |
|---|---|---|---|
| name | text | — | Always |
| memoryTrimmingMode | select | "message_count" | When memory=true. Options: message_count, token_budget, message_compacting, rag_retrieval |
| maxMessages | number | 10 | When memoryTrimmingMode=message_count |
| tokenBudget | number | 10000 | When memoryTrimmingMode=token_budget |
| conversationHistoryTokens | number | 5000 | When memoryTrimmingMode=token_budget |
| compactingThreshold | number | 20 | When memoryTrimmingMode=message_compacting |
| compactingKeepRecent | number | 10 | When memoryTrimmingMode=message_compacting |
| compactingModel | select | — | When memoryTrimmingMode=message_compacting |
| compactingImportantEntities | tags | — | When memoryTrimmingMode=message_compacting |
| ragTopK | number | — | When memoryTrimmingMode=rag_retrieval |
| ragRecentMessages | number | — | When memoryTrimmingMode=rag_retrieval |
| ragMaxHistoryHours | number | — | When memoryTrimmingMode=rag_retrieval |
| ragQueryContextMessages | number | — | When memoryTrimmingMode=rag_retrieval |
| ragGroupSize | number | — | When memoryTrimmingMode=rag_retrieval |
| ragGroupOverlap | number | — | When memoryTrimmingMode=rag_retrieval |
| ragPassthroughThreshold | number | — | When memoryTrimmingMode=rag_retrieval |

---

### llmModelNode — LLM Model
**Category:** AI
**Purpose:** Simple LLM call — sends system prompt + user prompt to a model. No tool calling or reasoning loops. Use for text generation, summarization, classification.
**Use cases:** Summarizing documents, classifying text, generating responses from templated prompts.

**Handlers:**
| ID | Type | Position | Compatibility |
|---|---|---|---|
| input | target | left | any |
| output | source | right | any |

**Required config:**
| Field | Type | Default | Description |
|---|---|---|---|
| providerId | select | — | LLM provider |
| systemPrompt | text | "" | System instructions |
| userPrompt | text | "{{source.message}}" | User input template |
| type | select | "Base" | Model type: "Base" or "Chain-of-Thought" |
| memory | boolean | false | Enable memory |

**Optional config:** Same memory sub-settings as agentNode (conditional on memoryTrimmingMode).

---

### templateNode — Template
**Category:** Processing
**Purpose:** Formats text using variable substitution. Variables: `{{source.field}}` for upstream node output, `{{session.field}}` for session state.
**Use cases:** Formatting agent output, building structured prompts, composing email bodies from extracted data.

**Handlers:**
| ID | Type | Position | Compatibility |
|---|---|---|---|
| input | target | left | any |
| output | source | right | any |

**Config:**
| Field | Type | Required | Description |
|---|---|---|---|
| template | text | Yes | Text with `{{variable}}` placeholders |
| name | text | No | Node name |

---

### toolBuilderNode — Tool Builder
**Category:** Processing
**Purpose:** Wraps a sub-flow (chain of nodes) as a callable tool for an agentNode. The agent decides when to invoke the tool based on its description. Connect `output_tool` → `agentNode.input_tools` and `starter_processor` → first sub-flow node.
**Use cases:** Wrapping a KB as a search tool, creating a database query tool, building custom API tools for agents.

**Handlers:**
| ID | Type | Position | Compatibility |
|---|---|---|---|
| output_tool | source | top | tools |
| starter_processor | source | bottom | any |
| end_processor | target | bottom | any |

**Config:**
| Field | Type | Required | Description |
|---|---|---|---|
| description | text | Yes | What this tool does — the agent reads this to decide when to call it |
| forwardTemplate | text | Yes | Template for returning data (default: "{}") |
| name | text | No | Node name |

---

### pythonCodeNode — Python Code
**Category:** Processing
**Purpose:** Executes custom Python code. Access input via `params.get('field_name')`. Returns the execution result.
**Use cases:** Custom data processing, calculations, string manipulation, API response parsing.

**Handlers:**
| ID | Type | Position | Compatibility |
|---|---|---|---|
| input | target | left | any |
| output | source | right | any |

**Config:**
| Field | Type | Required | Description |
|---|---|---|---|
| code | text | Yes | Python code to execute |
| name | text | No | Node name |
| unwrap | boolean | No | Return result directly without wrapping |

---

### dataMapperNode — Data Mapper
**Category:** Processing
**Purpose:** Transforms data structures using a Python script. Focused on reshaping/mapping data between nodes.
**Use cases:** Mapping API fields to a different schema, extracting fields from complex JSON, converting formats between integrations.

**Handlers:**
| ID | Type | Position | Compatibility |
|---|---|---|---|
| input | target | left | any |
| output | source | right | any |

**Config:**
| Field | Type | Required | Description |
|---|---|---|---|
| pythonScript | text | Yes | Python script for transformation |
| name | text | No | Node name |

---

### setStateNode — Set State
**Category:** Processing
**Purpose:** Sets or updates values in the workflow's session state. Downstream nodes access stored values via `{{session.key}}`.
**Use cases:** Storing user preferences, setting flags for routers, accumulating data across iterations.

**Handlers:**
| ID | Type | Position | Compatibility |
|---|---|---|---|
| input | target | left | any |
| output | source | right | any |

**Config:** Key-value state assignments configured via the workflow studio UI.

---

### routerNode — Router
**Category:** Control Flow
**Purpose:** Conditional branching. Does a SIMPLE STRING COMPARISON between two values and routes to `output_true` or `output_false`. It CANNOT do semantic analysis, topic detection, or intent classification — for that, use an llmModelNode or agentNode before the router to classify the input first, then route on the classification result.
**Use cases:** Routing based on classification output from an LLM, branching by email domain, checking flags set by upstream nodes.

**Handlers:**
| ID | Type | Position | Compatibility |
|---|---|---|---|
| input | target | left | any |
| output_true | source | right | any |
| output_false | source | right | any |

**Config:**
| Field | Type | Required | Description |
|---|---|---|---|
| first_value | text | Yes | Left side of comparison. Supports `{{source.field}}` |
| compare_condition | select | Yes | Condition operator (see below) |
| second_value | text | Yes | Right side of comparison |
| name | text | No | Node name |

**Available compare_condition values:**
- `equal` — exact match
- `not_equal` — not equal
- `contains` — first_value contains second_value
- `not_contain` — first_value does not contain second_value
- `starts_with` — first_value starts with second_value
- `not_starts_with` — first_value does not start with second_value
- `ends_with` — first_value ends with second_value
- `not_ends_with` — first_value does not end with second_value
- `regex` — second_value is a regex pattern to test against first_value

---

### aggregatorNode — Aggregator
**Category:** Control Flow
**Purpose:** Collects outputs from multiple upstream nodes and combines them. This is the ONLY node that accepts multiple incoming edges. Use to reconverge after branching or parallel paths.
**Use cases:** Merging parallel API results, collecting tool outputs, reconverging after router branches.

**Handlers:**
| ID | Type | Position | Compatibility |
|---|---|---|---|
| input | target | left | any |
| output | source | right | any |

**Config:**
| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| aggregationStrategy | select | Yes | "list" | How to combine: list, merge, concat |
| timeoutSeconds | number | No | 15 | Max wait time in seconds |
| name | text | No | — | Node name |
| forwardTemplate | text | No | — | Template for output formatting |
| requireAllInputs | boolean | No | true | Wait for all upstream nodes |

---

### humanInTheLoopNode — Human in the Loop
**Category:** Control Flow
**Purpose:** Pauses workflow execution and presents a form to the user for review/approval/input. Resumes after submission.
**Use cases:** Manager approval before creating tickets, user confirmation before sending email, human review of AI content.

**Handlers:**
| ID | Type | Position | Compatibility |
|---|---|---|---|
| input | target | left | any |
| output | source | right | any |

**Config:**
| Field | Type | Required | Description |
|---|---|---|---|
| message | text | No | Message to display to the user |
| form_fields | array | No | Form field definitions (name, type, label, required, placeholder, description, options) |
| ask_once | boolean | No | Only ask the user once (skip on subsequent runs) |

---

### workflowExecutorNode — Workflow Executor
**Category:** Control Flow
**Purpose:** Executes another workflow as a sub-workflow. Enables composition and reuse of workflows.
**Use cases:** Calling reusable sub-workflows, orchestrating multi-stage pipelines, modular workflow design.

**Handlers:**
| ID | Type | Position | Compatibility |
|---|---|---|---|
| input | target | left | any |
| output | source | right | any |

**Config:**
| Field | Type | Required | Description |
|---|---|---|---|
| workflowId | select | Yes | ID of the workflow to execute as a sub-workflow |
| inputParameters | object | No | Key-value parameters to pass to the sub-workflow (auto-detected from selected workflow's input schema) |
| workflowName | text | No | Display name of the selected workflow (auto-filled) |
| name | text | No | Node name |

---

### guardrailProvenanceNode — Guardrail: Provenance
**Category:** Utils
**Purpose:** Scores how well an answer is grounded in (supported by) provided context. Uses either embedding-based token overlap or an LLM judge to compute a provenance score. If the score falls below the threshold the node can block the workflow or substitute a fallback answer.
**Use cases:** Verifying RAG answers are grounded in retrieved documents, preventing hallucinated responses, enforcing factual accuracy before sending output to users.

**Handlers:**
| ID | Type | Position | Compatibility |
|---|---|---|---|
| input | target | left | any |
| output | source | right | any |

**Required config:**
| Field | Type | Default | Description |
|---|---|---|---|
| answer_field | text | "" | Key of the upstream field containing the answer text to check |
| context_field | text | "" | Key of the upstream field containing the context/source text |
| min_score | number | 0.5 | Minimum provenance score (0–1) to pass |

**Optional config:**
| Field | Type | Default | Condition | Description |
|---|---|---|---|---|
| name | text | "Guardrail Provenance" | Always | Node name |
| fail_on_violation | boolean | false | Always | Add `verdict="fail"` and `blocked=true` when score is below threshold |
| fallback_answer_enabled | boolean | false | Always | Use a fallback answer instead of blocking |
| fallback_answer | text | "" | fallback_answer_enabled=true | Text to substitute when a violation is detected |
| provenance_mode | select | "embeddings" | Always | Scoring method: "embeddings" (token overlap / embedding similarity) or "llm" (LLM judge) |
| embedding_type | select | "huggingface" | provenance_mode=embeddings | Embedding provider: "huggingface", "openai", or "bedrock" |
| embedding_model_name | text | "all-MiniLM-L6-v2" | provenance_mode=embeddings | Embedding model name |
| use_llm_judge | boolean | false | provenance_mode=llm | Use an LLM to compute the provenance score |
| llm_provider_id | select | "" | provenance_mode=llm | LLM provider for the judge; uses default if omitted |
| llm_judge_system_prompt_suffix | text | "" | provenance_mode=llm | Additional instructions appended to the judge system prompt |

**Output fields:**
| Field | Description |
|---|---|
| answer | Original answer or the fallback answer if substituted |
| context | The context text that was checked against |
| _guardrail_provenance | Object with: `type` ("provenance"), `score` (0–1), `threshold`, `verdict` ("pass" or "fail"), `heuristic_score`, optional `llm_judge` details, optional `fallback_used` |
| blocked | (optional) `true` if `fail_on_violation` triggered |
| verdict | (optional) `"provenance_fail"` if blocked |

---

### guardrailNliNode — Guardrail: NLI Fact-check
**Category:** Utils
**Purpose:** Runs Natural Language Inference (NLI) between an answer and evidence to determine if the answer is entailed by, contradicts, or is unknown relative to the evidence. Uses a local cross-encoder NLI model (falls back to heuristic if unavailable). Can block the workflow or substitute a fallback on contradiction.
**Use cases:** Fact-checking agent answers against source documents, detecting contradictions before responding, ensuring consistency between generated text and evidence.

**Handlers:**
| ID | Type | Position | Compatibility |
|---|---|---|---|
| input | target | left | any |
| output | source | right | any |

**Required config:**
| Field | Type | Default | Description |
|---|---|---|---|
| answer_field | text | "" | Key of the upstream field containing the answer text to check |
| evidence_field | text | "" | Key of the upstream field containing the evidence/context text |
| min_entail_score | number | 0.5 | Minimum entailment score (0–1) to pass |

**Optional config:**
| Field | Type | Default | Description |
|---|---|---|---|
| name | text | "Guardrail NLI" | Node name |
| nli_model_name | select | "cross-encoder/nli-deberta-v3-base" | NLI model. Options: "cross-encoder/nli-deberta-v3-base" (DeBERTa v3), "cross-encoder/nli-roberta-base" (RoBERTa) |
| fail_on_contradiction | boolean | false | Add `verdict="fail"` and `blocked=true` when contradiction detected |
| fallback_answer_enabled | boolean | false | Use a fallback answer instead of blocking |
| fallback_answer | text | "" | Text to substitute on contradiction (requires fallback_answer_enabled=true) |

**Output fields:**
| Field | Description |
|---|---|
| answer | Original answer or the fallback answer if substituted |
| evidence | The evidence text that was checked against |
| _guardrail_nli | Object with: `type` ("nli"), `entail_score` (0–1), `contradiction_score` (0–1), `threshold`, `verdict` ("entails", "contradicts", or "unknown"), optional `fallback_used` |
| blocked | (optional) `true` if `fail_on_contradiction` triggered |
| verdict | (optional) `"nli_contradiction"` if blocked |

---

### knowledgeBaseNode — Knowledge Base
**Category:** Knowledge
**Purpose:** Queries knowledge bases using RAG (Retrieval Augmented Generation). Searches indexed documents and returns relevant chunks. Usually wrapped by a toolBuilderNode to give agents KB access.
**Use cases:** Product documentation lookup, company policy search, FAQ retrieval, context injection before response generation.

**Handlers:**
| ID | Type | Position | Compatibility |
|---|---|---|---|
| input | target | left | any |
| output | source | right | any |

**Config:**
| Field | Type | Required | Description |
|---|---|---|---|
| query | text | Yes | Search query. Use `{{session.message}}` when wrapped as a tool |
| limit | number | Yes | Max results to return |
| force | boolean | Yes | Force the result limit |
| selectedBases | tags | Yes | Which knowledge base(s) to search |
| name | text | No | Node name |

---

### threadRAGNode — Thread RAG
**Category:** Knowledge
**Purpose:** Performs RAG over the current conversation thread. Indexes and retrieves relevant past messages from conversation history.
**Use cases:** Finding relevant past messages in long conversations, retrieving earlier context in multi-turn dialogue.

**Handlers:**
| ID | Type | Position | Compatibility |
|---|---|---|---|
| input | target | left | any |
| output | source | right | any |

**Config:**
| Field | Type | Required | Description |
|---|---|---|---|
| action | select | Yes | RAG action to perform |
| name | text | No | Node name |
| query | text | No | Search query |
| top_k | number | No | Number of results |
| message | text | No | Message to index |

---

### apiToolNode — API Tool
**Category:** Integration
**Purpose:** Makes HTTP API calls to external endpoints. Supports all standard HTTP methods.
**Use cases:** Fetching CRM data, sending webhooks, calling third-party services, data enrichment.

**Handlers:**
| ID | Type | Position | Compatibility |
|---|---|---|---|
| input | target | left | any |
| output | source | right | any |

**Config:**
| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| endpoint | text | Yes | — | Full URL of the API endpoint |
| method | select | Yes | "GET" | HTTP method: GET, POST, PUT, DELETE, PATCH |
| name | text | No | — | Node name |
| requestBody | text | No | — | JSON request body |
| headers | object | No | — | HTTP headers |
| parameters | object | No | — | Query parameters |

---

### openApiNode — Open API
**Category:** Integration
**Purpose:** Executes API calls based on an OpenAPI/Swagger specification. Uses an LLM to interpret natural language queries and select the correct endpoint.
**Use cases:** Querying complex APIs with plain English, auto-generating API calls, exploring documented endpoints.

**Handlers:**
| ID | Type | Position | Compatibility |
|---|---|---|---|
| input | target | left | any |
| output | source | right | any |

**Config:**
| Field | Type | Required | Description |
|---|---|---|---|
| providerId | select | Yes | LLM provider for query interpretation |
| originalFileName | text | Yes | OpenAPI specification file |
| query | text | Yes | Natural language query |
| name | text | No | Node name |

---

### slackMessageNode — Slack Message
**Category:** Integration
**Purpose:** Sends messages to a Slack channel. Requires Slack integration to be configured.
**Use cases:** Team notifications, workflow alerts, posting AI summaries to channels.

**Handlers:**
| ID | Type | Position | Compatibility |
|---|---|---|---|
| input | target | left | any |
| output | source | right | any |

**Config:**
| Field | Type | Required | Description |
|---|---|---|---|
| app_settings_id | select | Yes | Slack integration configuration |
| channel | text | Yes | Slack channel ID |
| message | text | Yes | Message text to send |
| name | text | No | Node name |

---

### gmailNode — Gmail
**Category:** Integration
**Purpose:** Interacts with Gmail — send emails, read messages, reply, search, mark as read, or delete. Requires Gmail data source configuration.
**Use cases:** Automated response emails, email processing pipelines, inbox monitoring, email-triggered workflows.

**Handlers:**
| ID | Type | Position | Compatibility |
|---|---|---|---|
| input | target | left | any |
| output | source | right | any |

**Config:**
| Field | Type | Required | Description |
|---|---|---|---|
| dataSourceId | select | Yes | Gmail data source connector |
| operation | select | Yes | Operation: send_email, get_messages, mark_as_read, delete_message, reply_to_email, search_emails |
| to | text | Yes* | Recipient email (*for send_email) |
| subject | text | Yes* | Email subject (*for send_email) |
| body | text | Yes* | Email body (*for send_email) |
| name | text | No | Node name |
| cc | text | No | CC recipients |
| bcc | text | No | BCC recipients |

---

### readMailsNode — Read Mails
**Category:** Integration
**Purpose:** Reads emails from Gmail with search filters. Requires Gmail data source configuration.
**Use cases:** Processing unread customer emails, fetching labeled emails for classification, inbox monitoring.

**Handlers:**
| ID | Type | Position | Compatibility |
|---|---|---|---|
| input | target | left | any |
| output | source | right | any |

**Config:**
| Field | Type | Required | Description |
|---|---|---|---|
| dataSourceId | select | Yes | Gmail data source |
| name | text | No | Node name |
| searchCriteria.from | text | No | Filter by sender |
| searchCriteria.to | text | No | Filter by recipient |
| searchCriteria.subject | text | No | Subject contains |
| searchCriteria.label | select | No | Gmail label filter |
| searchCriteria.newer_than | select | No | Messages newer than |
| searchCriteria.older_than | select | No | Messages older than |
| searchCriteria.max_results | number | No | Max messages to return |
| searchCriteria.has_attachment | boolean | No | Filter by attachment |
| searchCriteria.is_unread | boolean | No | Unread only |
| searchCriteria.custom_query | text | No | Custom Gmail search query |

---

### whatsappToolNode — WhatsApp
**Category:** Integration
**Purpose:** Sends WhatsApp messages. Requires WhatsApp integration configuration.
**Use cases:** Order confirmations, customer notifications, automated outreach.

**Handlers:**
| ID | Type | Position | Compatibility |
|---|---|---|---|
| input | target | left | any |

**Config:**
| Field | Type | Required | Description |
|---|---|---|---|
| app_settings_id | select | Yes | WhatsApp integration settings |
| recipient_number | text | Yes | Recipient phone number |
| message | text | Yes | Message text |
| name | text | No | Node name |

---

### zendeskTicketNode — Zendesk Ticket
**Category:** Integration
**Purpose:** Creates support tickets in Zendesk. Requires Zendesk integration configuration.
**Use cases:** Auto-creating tickets from chat, escalating AI-detected issues, tickets with AI-extracted metadata.

**Handlers:**
| ID | Type | Position | Compatibility |
|---|---|---|---|
| input | target | left | any |

**Config:**
| Field | Type | Required | Description |
|---|---|---|---|
| app_settings_id | select | Yes | Zendesk integration settings |
| subject | text | Yes | Ticket subject |
| description | text | Yes | Ticket description |
| requester_name | text | No | Requester's name |
| requester_email | text | No | Requester's email |
| name | text | No | Node name |
| tags | tags | No | Ticket tags |
| custom_fields | array | No | Custom Zendesk fields (array of {id, value} objects) |

---

### calendarEventNode — Calendar Event
**Category:** Integration
**Purpose:** Creates or reads Google Calendar events. Requires Calendar data source configuration.
**Use cases:** Scheduling meetings from AI conversations, creating follow-up reminders, checking availability.

**Handlers:**
| ID | Type | Position | Compatibility |
|---|---|---|---|
| input | target | left | any |
| output | source | right | any |

**Config:**
| Field | Type | Required | Description |
|---|---|---|---|
| dataSourceId | select | Yes | Calendar data source connector |
| operation | select | Yes | "create_calendar_event" or "search_calendar_events" |
| summary | text | Yes* | Event summary/title (*for create operation) |
| start | text | Yes | Start datetime in ISO format |
| end | text | Yes | End datetime in ISO format |
| timezone | text | No | Timezone for datetime parsing (default: browser timezone, falls back to UTC) |
| name | text | No | Node name |
| subjectContains | text | No | Search filter for reading events |
| attendee | text | No | Attendee email filter (search operation only) |
| max_results | number | No | Maximum search results (default: 10) |

---

### jiraNode — Jira
**Category:** Integration
**Purpose:** Creates tasks/issues in Jira. Requires Jira integration configuration.
**Use cases:** Bug reports from customer feedback, task tickets from AI analysis, urgent issue escalation.

**Handlers:**
| ID | Type | Position | Compatibility |
|---|---|---|---|
| input | target | left | any |
| output | source | right | any |

**Config:**
| Field | Type | Required | Description |
|---|---|---|---|
| app_settings_id | select | Yes | Jira integration settings |
| spaceKey | text | Yes | Jira project/space key |
| taskName | text | Yes | Task/issue name |
| name | text | No | Node name |
| taskDescription | text | No | Task description |

---

### sqlNode — SQL
**Category:** Integration
**Purpose:** Executes SQL queries against a database. Supports writing SQL manually or generating SQL from natural language using an LLM.
**Use cases:** Querying customer data, running analytics, natural language to SQL.

**Handlers:**
| ID | Type | Position | Compatibility |
|---|---|---|---|
| input | target | left | any |
| output | source | right | any |

**Config:**
| Field | Type | Required | Condition | Description |
|---|---|---|---|---|
| dataSourceId | select | Yes | Always | Database data source |
| mode | select | Yes | Always | "sqlQuery" (manual) or "humanQuery" (AI-generated) |
| sqlQuery | text | Yes | mode=sqlQuery | SQL query to execute |
| providerId | select | Yes | mode=humanQuery | LLM provider for SQL generation |
| humanQuery | text | Yes | mode=humanQuery | Plain English query |
| name | text | No | Always | Node name |
| systemPrompt | text | No | mode=humanQuery | Custom instructions for SQL generation |

---

### mcpNode — MCP
**Category:** Integration
**Purpose:** Connects to an MCP (Model Context Protocol) server for external tools and resources.
**Use cases:** Integrating with MCP-compatible tool servers, using external MCP resources.

**Handlers:**
| ID | Type | Position | Compatibility |
|---|---|---|---|
| input | target | left | any |
| output | source | right | any |

**Config:**
| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| connectionType | select | Yes | "http" | Connection type: "stdio", "sse", or "http" |
| connectionConfig | object | Yes | — | Connection settings (see below) |
| name | text | No | "MCP Server" | Node name |
| description | text | No | — | Description of what this MCP server provides |
| availableTools | array | No | [] | List of tools discovered from the MCP server (auto-populated) |
| whitelistedTools | array | No | [] | Tool names to expose to the agent |
| returnDirect | boolean | No | false | Whether tool results are returned directly |

**connectionConfig for `stdio`:**
| Field | Type | Required | Description |
|---|---|---|---|
| command | text | Yes | Command to run the MCP server |
| args | array | No | Command arguments |
| env | object | No | Environment variables |

**connectionConfig for `http` / `sse`:**
| Field | Type | Required | Description |
|---|---|---|---|
| url | text | Yes | MCP server URL |
| api_key | text | No | API key for authentication |
| headers | object | No | Custom HTTP headers |
| timeout | number | No | Request timeout in seconds (default: 30) |

---

### mlModelInferenceNode — ML Model Inference
**Category:** ML
**Purpose:** Runs inference on a previously trained ML model. Select a trained model and pass input data for predictions.
**Use cases:** Customer churn prediction, sentiment analysis, product recommendations.

**Handlers:**
| ID | Type | Position | Compatibility |
|---|---|---|---|
| input | target | left | any |
| output | source | right | any |

**Config:**
| Field | Type | Required | Description |
|---|---|---|---|
| modelId | select | Yes | Trained ML model to use |
| modelName | text | No | Display name (auto-filled from selected model) |
| inferenceInputs | object | No | Dynamic feature inputs for prediction (Record of field name → value) |
| name | text | No | Node name |

---

### trainDataSourceNode — Train Data Source
**Category:** ML
**Purpose:** Loads training data from a data source for ML training pipelines.
**Use cases:** Loading CSV datasets, querying databases for training data.

**Handlers:**
| ID | Type | Position | Compatibility |
|---|---|---|---|
| input | target | left | any |
| output | source | right | any |

**Config:**
| Field | Type | Required | Description |
|---|---|---|---|
| sourceType | select | Yes | Type of data source: "datasource" (database) or "csv" (file upload) |
| name | text | No | Node name |
| dataSourceId | select | No | Data source ID (required when sourceType="datasource") |
| query | text | No | SQL query for data extraction (required when sourceType="datasource") |
| csvFileName | text | No | Name of the uploaded CSV file (when sourceType="csv") |
| csvFilePath | text | No | Server path to the uploaded CSV file |
| csvFileId | text | No | ID of the uploaded CSV file |
| csvFileUrl | text | No | URL of the uploaded CSV file |

---

### preprocessingNode — Preprocessing
**Category:** ML
**Purpose:** Preprocesses data for ML model training. Applies transformations using custom Python code.
**Use cases:** Data cleaning, feature engineering, handling missing values and outliers.

**Handlers:**
| ID | Type | Position | Compatibility |
|---|---|---|---|
| input | target | left | any |
| output | source | right | any |

**Config:**
| Field | Type | Required | Description |
|---|---|---|---|
| pythonCode | text | Yes | Custom preprocessing Python code |
| fileUrl | text | No | URL of the training data file (auto-filled from upstream node via `{{source.data_path}}`) |
| name | text | No | Node name |

---

### trainModelNode — Train Model
**Category:** ML
**Purpose:** Trains an ML model on preprocessed data. Configure model type, features, target, and validation split.
**Use cases:** Classification models, regression models, custom NLP models.

**Handlers:**
| ID | Type | Position | Compatibility |
|---|---|---|---|
| input | target | left | any |
| output | source | right | any |

**Config:**
| Field | Type | Required | Description |
|---|---|---|---|
| fileUrl | text | Yes | Training data file URL |
| modelType | select | Yes | Model: xgboost, random_forest, linear_regression, logistic_regression, neural_network |
| targetColumn | text | Yes | Target variable column name |
| featureColumns | tags | Yes | Feature column names |
| validationSplit | number | Yes | Train/test split ratio (default: 0.2, range: 0.1–0.5) |
| name | text | No | Node name |
| modelParameters | object | No | Model-specific hyperparameters |

---

## Workflow JSON Output Format

When creating a workflow, output JSON with this structure:

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
        "systemPrompt": "You are a customer support agent for Acme Corp...",
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
    {"from": "1", "to": "2"},
    {"from": "2", "to": "3"}
  ]
}
```

**Rules:**
- `uniqueId`: simple string ("1", "2", "3", ...)
- `node_name`: must match a node type key from this document
- `function_of_node`: human-readable label describing the node's role
- `config`: only include fields you want to override from defaults
- Edge `sourceHandle` defaults to "output", `targetHandle` defaults to "input"
- Tool edges: `sourceHandle: "output_tool"`, `targetHandle: "input_tools"`
- Router edges: `sourceHandle: "output_true"` or `"output_false"`
- Tool sub-flow edges: `sourceHandle: "starter_processor"`, `targetHandle: "input"`
