# GenAssist Workflow Examples

This document contains curated, correct workflow examples for common use cases. Each example shows the simplified workflow JSON format that the Workflow Builder Agent outputs.

---

## Example 1: Simple Chatbot

**Use case**: A basic conversational AI agent with memory.

**Architecture**: chatInput → agent → chatOutput

```json
{
  "workflow": [
    {"uniqueId": "1", "node_name": "chatInputNode", "function_of_node": "Chat Input"},
    {"uniqueId": "2", "node_name": "agentNode", "function_of_node": "Support Agent", "config": {
      "systemPrompt": "You are a friendly customer support agent for Acme Corp. Help customers with their questions about products, orders, and account issues. Be concise and helpful.",
      "userPrompt": "{{source.message}}",
      "type": "ToolSelector",
      "memory": true,
      "maxIterations": 5
    }},
    {"uniqueId": "3", "node_name": "chatOutputNode", "function_of_node": "Chat Output"}
  ],
  "edges": [
    {"from": "1", "to": "2"},
    {"from": "2", "to": "3"}
  ]
}
```

---

## Example 2: Chatbot with Knowledge Base

**Use case**: An agent that can search a knowledge base to answer questions.

**Architecture**: chatInput → agent → chatOutput, with toolBuilder → knowledgeBase as agent tool

**CRITICAL**: Tool connections go FROM toolBuilderNode TO agentNode (not reverse). Every tool needs TWO edges: output_tool→input_tools AND starter_processor→sub_node.input.

```json
{
  "workflow": [
    {"uniqueId": "1", "node_name": "chatInputNode", "function_of_node": "Chat Input"},
    {"uniqueId": "2", "node_name": "agentNode", "function_of_node": "Support Agent", "config": {
      "systemPrompt": "You are a support agent for Acme Corp. Use the knowledge base tool to look up product information, policies, and FAQs before answering. Always cite the source when using KB results.",
      "userPrompt": "{{source.message}}",
      "type": "ToolSelector",
      "memory": true,
      "maxIterations": 5
    }},
    {"uniqueId": "3", "node_name": "chatOutputNode", "function_of_node": "Chat Output"},
    {"uniqueId": "4", "node_name": "toolBuilderNode", "function_of_node": "KB Tool", "config": {
      "name": "Product Knowledge Base",
      "description": "Search the knowledge base for product information, FAQs, and company policies"
    }},
    {"uniqueId": "5", "node_name": "knowledgeBaseNode", "function_of_node": "Product KB", "config": {
      "query": "{{session.message}}",
      "limit": 5
    }}
  ],
  "edges": [
    {"from": "1", "to": "2"},
    {"from": "2", "to": "3"},
    {"from": "4", "to": "2", "sourceHandle": "output_tool", "targetHandle": "input_tools"},
    {"from": "4", "to": "5", "sourceHandle": "starter_processor", "targetHandle": "input"}
  ]
}
```

---

## Example 3: Topic-Based Routing (Guardrail Pattern)

**Use case**: Filter on-topic vs off-topic messages before reaching the main agent. Reject off-topic messages with a polite template.

**Architecture**: chatInput → llmModel (classifier) → router → [agent branch | rejection branch], each with its own chatOutput

**CRITICAL**: routerNode does SIMPLE STRING COMPARISON only. It CANNOT understand topics or intent. An llmModelNode must classify FIRST, then the router checks the classification string.

```json
{
  "workflow": [
    {"uniqueId": "1", "node_name": "chatInputNode", "function_of_node": "Chat Input"},
    {"uniqueId": "2", "node_name": "llmModelNode", "function_of_node": "Topic Classifier", "config": {
      "systemPrompt": "You are a topic classifier. If the user's message is about customer support, orders, or products, respond with exactly: on_topic\nIf it is about anything else, respond with exactly: off_topic\nRespond with ONLY one of these two words, nothing else.",
      "userPrompt": "{{source.message}}"
    }},
    {"uniqueId": "3", "node_name": "routerNode", "function_of_node": "Topic Router", "config": {
      "first_value": "{{source.message}}",
      "compare_condition": "contains",
      "second_value": "on_topic"
    }},
    {"uniqueId": "4", "node_name": "agentNode", "function_of_node": "Support Agent", "config": {
      "systemPrompt": "You are a customer support agent. Help users with orders, products, and account issues.",
      "userPrompt": "{{source.message}}",
      "type": "ToolSelector",
      "memory": true,
      "maxIterations": 5
    }},
    {"uniqueId": "5", "node_name": "chatOutputNode", "function_of_node": "Support Output"},
    {"uniqueId": "6", "node_name": "templateNode", "function_of_node": "Rejection Message", "config": {
      "template": "I'm sorry, I can only help with customer support topics like orders, products, and account issues. Please rephrase your question or contact us through another channel for other inquiries."
    }},
    {"uniqueId": "7", "node_name": "chatOutputNode", "function_of_node": "Rejection Output"}
  ],
  "edges": [
    {"from": "1", "to": "2"},
    {"from": "2", "to": "3"},
    {"from": "3", "to": "4", "sourceHandle": "output_true", "targetHandle": "input"},
    {"from": "3", "to": "6", "sourceHandle": "output_false", "targetHandle": "input"},
    {"from": "4", "to": "5"},
    {"from": "6", "to": "7"}
  ]
}
```

---

## Example 4: Guardrail + Knowledge Base

**Use case**: Topic filter that rejects off-topic messages, with a KB-powered agent for on-topic ones.

**Architecture**: Combines the guardrail pattern with the KB pattern.

```json
{
  "workflow": [
    {"uniqueId": "1", "node_name": "chatInputNode", "function_of_node": "Chat Input"},
    {"uniqueId": "2", "node_name": "llmModelNode", "function_of_node": "Topic Classifier", "config": {
      "systemPrompt": "Classify if the message is about HR policies, benefits, or company procedures. Respond with exactly: on_topic or off_topic",
      "userPrompt": "{{source.message}}"
    }},
    {"uniqueId": "3", "node_name": "routerNode", "function_of_node": "Topic Router", "config": {
      "first_value": "{{source.message}}",
      "compare_condition": "contains",
      "second_value": "on_topic"
    }},
    {"uniqueId": "4", "node_name": "agentNode", "function_of_node": "HR Assistant", "config": {
      "systemPrompt": "You are an HR assistant. Use the knowledge base to answer questions about company policies, benefits, and procedures. Always provide accurate information from the KB.",
      "userPrompt": "{{source.message}}",
      "type": "ToolSelector",
      "memory": true,
      "maxIterations": 5
    }},
    {"uniqueId": "5", "node_name": "chatOutputNode", "function_of_node": "HR Output"},
    {"uniqueId": "6", "node_name": "templateNode", "function_of_node": "Off-Topic Response", "config": {
      "template": "I can only help with HR-related questions like company policies, benefits, and procedures. Please ask an HR-related question."
    }},
    {"uniqueId": "7", "node_name": "chatOutputNode", "function_of_node": "Rejection Output"},
    {"uniqueId": "8", "node_name": "toolBuilderNode", "function_of_node": "KB Tool", "config": {
      "name": "HR Policies KB",
      "description": "Search the knowledge base for HR policies, benefits information, and company procedures"
    }},
    {"uniqueId": "9", "node_name": "knowledgeBaseNode", "function_of_node": "HR Knowledge Base", "config": {
      "query": "{{session.message}}",
      "limit": 5
    }}
  ],
  "edges": [
    {"from": "1", "to": "2"},
    {"from": "2", "to": "3"},
    {"from": "3", "to": "4", "sourceHandle": "output_true", "targetHandle": "input"},
    {"from": "3", "to": "6", "sourceHandle": "output_false", "targetHandle": "input"},
    {"from": "4", "to": "5"},
    {"from": "6", "to": "7"},
    {"from": "8", "to": "4", "sourceHandle": "output_tool", "targetHandle": "input_tools"},
    {"from": "8", "to": "9", "sourceHandle": "starter_processor", "targetHandle": "input"}
  ]
}
```

---

## Example 5: Agent with Slack Integration

**Use case**: An agent that processes user requests and sends notifications to Slack.

**Architecture**: chatInput → agent → chatOutput, with toolBuilder → slackMessage as agent tool

```json
{
  "workflow": [
    {"uniqueId": "1", "node_name": "chatInputNode", "function_of_node": "Chat Input"},
    {"uniqueId": "2", "node_name": "agentNode", "function_of_node": "Notification Agent", "config": {
      "systemPrompt": "You are a notification agent. When the user reports an issue or requests help, use the Slack tool to notify the support team. Summarize the issue clearly in the Slack message. Confirm to the user that the team has been notified.",
      "userPrompt": "{{source.message}}",
      "type": "ToolSelector",
      "memory": true,
      "maxIterations": 5
    }},
    {"uniqueId": "3", "node_name": "chatOutputNode", "function_of_node": "Chat Output"},
    {"uniqueId": "4", "node_name": "toolBuilderNode", "function_of_node": "Slack Tool", "config": {
      "name": "Slack Notification",
      "description": "Send a notification message to the support team Slack channel"
    }},
    {"uniqueId": "5", "node_name": "slackMessageNode", "function_of_node": "Send Slack Message", "config": {
      "channel": "#support-alerts",
      "message": "{{session.message}}"
    }}
  ],
  "edges": [
    {"from": "1", "to": "2"},
    {"from": "2", "to": "3"},
    {"from": "4", "to": "2", "sourceHandle": "output_tool", "targetHandle": "input_tools"},
    {"from": "4", "to": "5", "sourceHandle": "starter_processor", "targetHandle": "input"}
  ]
}
```

---

## Example 6: Agent with Jira Integration

**Use case**: An agent that can create and manage Jira tickets based on user requests.

**Architecture**: chatInput → agent → chatOutput, with toolBuilder → jiraNode as agent tool

```json
{
  "workflow": [
    {"uniqueId": "1", "node_name": "chatInputNode", "function_of_node": "Chat Input"},
    {"uniqueId": "2", "node_name": "agentNode", "function_of_node": "Jira Agent", "config": {
      "systemPrompt": "You are a project management assistant. Help users create Jira tickets for bugs, features, and tasks. Ask for the ticket summary, description, and priority before creating. Use the Jira tool to create the ticket.",
      "userPrompt": "{{source.message}}",
      "type": "ToolSelector",
      "memory": true,
      "maxIterations": 5
    }},
    {"uniqueId": "3", "node_name": "chatOutputNode", "function_of_node": "Chat Output"},
    {"uniqueId": "4", "node_name": "toolBuilderNode", "function_of_node": "Jira Tool", "config": {
      "name": "Jira Ticket Creator",
      "description": "Create a new Jira ticket with the specified summary, description, and priority"
    }},
    {"uniqueId": "5", "node_name": "jiraNode", "function_of_node": "Create Jira Ticket", "config": {
      "operation": "create_issue"
    }}
  ],
  "edges": [
    {"from": "1", "to": "2"},
    {"from": "2", "to": "3"},
    {"from": "4", "to": "2", "sourceHandle": "output_tool", "targetHandle": "input_tools"},
    {"from": "4", "to": "5", "sourceHandle": "starter_processor", "targetHandle": "input"}
  ]
}
```

---

## Example 7: Agent with Multiple Tools (KB + Zendesk)

**Use case**: A support agent that can search a knowledge base AND create Zendesk tickets.

**Architecture**: chatInput → agent → chatOutput, with two toolBuilder nodes (one for KB, one for Zendesk)

**CRITICAL**: Each toolBuilderNode wraps exactly ONE sub-node. To give an agent multiple tools, use multiple toolBuilderNodes, each with its own sub-node and both required edges.

```json
{
  "workflow": [
    {"uniqueId": "1", "node_name": "chatInputNode", "function_of_node": "Chat Input"},
    {"uniqueId": "2", "node_name": "agentNode", "function_of_node": "Support Agent", "config": {
      "systemPrompt": "You are a support agent. First search the knowledge base for answers. If you can resolve the issue, do so. If the issue requires escalation, create a Zendesk ticket with the details.",
      "userPrompt": "{{source.message}}",
      "type": "ToolSelector",
      "memory": true,
      "maxIterations": 10
    }},
    {"uniqueId": "3", "node_name": "chatOutputNode", "function_of_node": "Chat Output"},
    {"uniqueId": "4", "node_name": "toolBuilderNode", "function_of_node": "KB Tool", "config": {
      "name": "Support Knowledge Base",
      "description": "Search the knowledge base for product documentation, troubleshooting guides, and FAQs"
    }},
    {"uniqueId": "5", "node_name": "knowledgeBaseNode", "function_of_node": "Support KB", "config": {
      "query": "{{session.message}}",
      "limit": 5
    }},
    {"uniqueId": "6", "node_name": "toolBuilderNode", "function_of_node": "Zendesk Tool", "config": {
      "name": "Zendesk Ticket Creator",
      "description": "Create a Zendesk support ticket for issues that need escalation to the human support team"
    }},
    {"uniqueId": "7", "node_name": "zendeskTicketNode", "function_of_node": "Create Zendesk Ticket"}
  ],
  "edges": [
    {"from": "1", "to": "2"},
    {"from": "2", "to": "3"},
    {"from": "4", "to": "2", "sourceHandle": "output_tool", "targetHandle": "input_tools"},
    {"from": "4", "to": "5", "sourceHandle": "starter_processor", "targetHandle": "input"},
    {"from": "6", "to": "2", "sourceHandle": "output_tool", "targetHandle": "input_tools"},
    {"from": "6", "to": "7", "sourceHandle": "starter_processor", "targetHandle": "input"}
  ]
}
```

---

## Example 8: Formatted Output with Template

**Use case**: An agent whose response is formatted through a template before being shown to the user.

**Architecture**: chatInput → agent → template → chatOutput

```json
{
  "workflow": [
    {"uniqueId": "1", "node_name": "chatInputNode", "function_of_node": "Chat Input"},
    {"uniqueId": "2", "node_name": "agentNode", "function_of_node": "Research Agent", "config": {
      "systemPrompt": "You are a research assistant. Provide detailed, factual answers to user questions. Focus on accuracy and clarity.",
      "userPrompt": "{{source.message}}",
      "type": "ToolSelector",
      "memory": true,
      "maxIterations": 5
    }},
    {"uniqueId": "3", "node_name": "templateNode", "function_of_node": "Format Response", "config": {
      "template": "## Research Results\n\n{{source.message}}\n\n---\n*Generated by Research Assistant*"
    }},
    {"uniqueId": "4", "node_name": "chatOutputNode", "function_of_node": "Chat Output"}
  ],
  "edges": [
    {"from": "1", "to": "2"},
    {"from": "2", "to": "3"},
    {"from": "3", "to": "4"}
  ]
}
```

---

## Example 9: Human-in-the-Loop Approval

**Use case**: An agent that drafts actions but requires human approval before executing them.

**Architecture**: chatInput → agent → humanInTheLoop → action node → chatOutput

```json
{
  "workflow": [
    {"uniqueId": "1", "node_name": "chatInputNode", "function_of_node": "Chat Input"},
    {"uniqueId": "2", "node_name": "agentNode", "function_of_node": "Draft Agent", "config": {
      "systemPrompt": "You are an email drafting assistant. Help the user compose professional emails. Draft the email based on their request. The email will be reviewed by a human before sending.",
      "userPrompt": "{{source.message}}",
      "type": "ToolSelector",
      "memory": true,
      "maxIterations": 5
    }},
    {"uniqueId": "3", "node_name": "humanInTheLoopNode", "function_of_node": "Manager Approval", "config": {
      "title": "Email Draft Review",
      "description": "Please review the drafted email before it is sent.",
      "assignee": "manager@company.com"
    }},
    {"uniqueId": "4", "node_name": "gmailNode", "function_of_node": "Send Email", "config": {
      "operation": "send_email"
    }},
    {"uniqueId": "5", "node_name": "chatOutputNode", "function_of_node": "Chat Output"}
  ],
  "edges": [
    {"from": "1", "to": "2"},
    {"from": "2", "to": "3"},
    {"from": "3", "to": "4"},
    {"from": "4", "to": "5"}
  ]
}
```

---

## Example 10: Multi-Branch Routing (3 departments)

**Use case**: Route user messages to different agents based on the department (sales, support, billing).

**Architecture**: chatInput → llmModel (classifier) → router chain → department agents → separate chatOutputs

**CRITICAL**: Each branch MUST have its own chatOutputNode. Never merge branches into a single output.

```json
{
  "workflow": [
    {"uniqueId": "1", "node_name": "chatInputNode", "function_of_node": "Chat Input"},
    {"uniqueId": "2", "node_name": "llmModelNode", "function_of_node": "Department Classifier", "config": {
      "systemPrompt": "Classify the user's message into one of these departments: sales, support, or billing. Respond with ONLY the department name in lowercase, nothing else.",
      "userPrompt": "{{source.message}}"
    }},
    {"uniqueId": "3", "node_name": "routerNode", "function_of_node": "Sales Check", "config": {
      "first_value": "{{source.message}}",
      "compare_condition": "contains",
      "second_value": "sales"
    }},
    {"uniqueId": "4", "node_name": "agentNode", "function_of_node": "Sales Agent", "config": {
      "systemPrompt": "You are a sales representative. Help customers with pricing, product demos, and purchase decisions.",
      "userPrompt": "{{source.message}}",
      "type": "ToolSelector",
      "memory": true,
      "maxIterations": 5
    }},
    {"uniqueId": "5", "node_name": "chatOutputNode", "function_of_node": "Sales Output"},
    {"uniqueId": "6", "node_name": "routerNode", "function_of_node": "Support Check", "config": {
      "first_value": "{{source.message}}",
      "compare_condition": "contains",
      "second_value": "support"
    }},
    {"uniqueId": "7", "node_name": "agentNode", "function_of_node": "Support Agent", "config": {
      "systemPrompt": "You are a technical support agent. Help customers troubleshoot issues and resolve problems.",
      "userPrompt": "{{source.message}}",
      "type": "ToolSelector",
      "memory": true,
      "maxIterations": 5
    }},
    {"uniqueId": "8", "node_name": "chatOutputNode", "function_of_node": "Support Output"},
    {"uniqueId": "9", "node_name": "agentNode", "function_of_node": "Billing Agent", "config": {
      "systemPrompt": "You are a billing specialist. Help customers with invoices, payment issues, and subscription management.",
      "userPrompt": "{{source.message}}",
      "type": "ToolSelector",
      "memory": true,
      "maxIterations": 5
    }},
    {"uniqueId": "10", "node_name": "chatOutputNode", "function_of_node": "Billing Output"}
  ],
  "edges": [
    {"from": "1", "to": "2"},
    {"from": "2", "to": "3"},
    {"from": "3", "to": "4", "sourceHandle": "output_true", "targetHandle": "input"},
    {"from": "3", "to": "6", "sourceHandle": "output_false", "targetHandle": "input"},
    {"from": "4", "to": "5"},
    {"from": "6", "to": "7", "sourceHandle": "output_true", "targetHandle": "input"},
    {"from": "6", "to": "9", "sourceHandle": "output_false", "targetHandle": "input"},
    {"from": "7", "to": "8"},
    {"from": "9", "to": "10"}
  ]
}
```

---

## Example 11: Gmail Automation with KB

**Use case**: An agent that reads emails, searches a KB for relevant info, and drafts replies.

```json
{
  "workflow": [
    {"uniqueId": "1", "node_name": "chatInputNode", "function_of_node": "Chat Input"},
    {"uniqueId": "2", "node_name": "agentNode", "function_of_node": "Email Assistant", "config": {
      "systemPrompt": "You are an email assistant. You can read the user's recent emails and search the knowledge base to draft informed replies. When the user asks about an email, read it first, then search the KB if needed, and help compose a reply.",
      "userPrompt": "{{source.message}}",
      "type": "ToolSelector",
      "memory": true,
      "maxIterations": 10
    }},
    {"uniqueId": "3", "node_name": "chatOutputNode", "function_of_node": "Chat Output"},
    {"uniqueId": "4", "node_name": "toolBuilderNode", "function_of_node": "Read Emails Tool", "config": {
      "name": "Read Emails",
      "description": "Read the user's recent emails from Gmail"
    }},
    {"uniqueId": "5", "node_name": "readMailsNode", "function_of_node": "Read Gmail"},
    {"uniqueId": "6", "node_name": "toolBuilderNode", "function_of_node": "KB Tool", "config": {
      "name": "Company Knowledge Base",
      "description": "Search the company knowledge base for relevant information to help draft email replies"
    }},
    {"uniqueId": "7", "node_name": "knowledgeBaseNode", "function_of_node": "Company KB", "config": {
      "query": "{{session.message}}",
      "limit": 5
    }},
    {"uniqueId": "8", "node_name": "toolBuilderNode", "function_of_node": "Send Email Tool", "config": {
      "name": "Send Email",
      "description": "Send an email reply via Gmail"
    }},
    {"uniqueId": "9", "node_name": "gmailNode", "function_of_node": "Send Gmail", "config": {
      "operation": "send_email"
    }}
  ],
  "edges": [
    {"from": "1", "to": "2"},
    {"from": "2", "to": "3"},
    {"from": "4", "to": "2", "sourceHandle": "output_tool", "targetHandle": "input_tools"},
    {"from": "4", "to": "5", "sourceHandle": "starter_processor", "targetHandle": "input"},
    {"from": "6", "to": "2", "sourceHandle": "output_tool", "targetHandle": "input_tools"},
    {"from": "6", "to": "7", "sourceHandle": "starter_processor", "targetHandle": "input"},
    {"from": "8", "to": "2", "sourceHandle": "output_tool", "targetHandle": "input_tools"},
    {"from": "8", "to": "9", "sourceHandle": "starter_processor", "targetHandle": "input"}
  ]
}
```

---

## Example 12: State Management with SetState

**Use case**: An agent that saves conversation context into session state for downstream use.

**Architecture**: chatInput → agent → setState → chatOutput

```json
{
  "workflow": [
    {"uniqueId": "1", "node_name": "chatInputNode", "function_of_node": "Chat Input"},
    {"uniqueId": "2", "node_name": "agentNode", "function_of_node": "Intake Agent", "config": {
      "systemPrompt": "You are an intake agent. Collect the user's name, email, and issue description. Once you have all three, summarize them in a structured format.",
      "userPrompt": "{{source.message}}",
      "type": "ToolSelector",
      "memory": true,
      "maxIterations": 5
    }},
    {"uniqueId": "3", "node_name": "setStateNode", "function_of_node": "Save Context", "config": {
      "values": [
        {"key": "intake_summary", "value": "{{source.message}}"}
      ]
    }},
    {"uniqueId": "4", "node_name": "chatOutputNode", "function_of_node": "Chat Output"}
  ],
  "edges": [
    {"from": "1", "to": "2"},
    {"from": "2", "to": "3"},
    {"from": "3", "to": "4"}
  ]
}
```

---

## Key Rules Reinforced by These Examples

1. **Single Input Rule**: Every node accepts ONLY ONE incoming edge (except aggregatorNode).
2. **Separate Outputs**: Each branch after a router MUST have its own chatOutputNode.
3. **Tool Direction**: Tools connect FROM toolBuilderNode TO agentNode, never the reverse.
4. **Two Edges Per Tool**: Every toolBuilderNode needs: output_tool→input_tools AND starter_processor→sub_node.input.
5. **Router Limitation**: routerNode does simple string comparison only. Use llmModelNode first for topic/intent classification.
6. **userPrompt**: Always set to `{{source.message}}` on agent and LLM nodes. Never null or literal text.
7. **Dedicated Nodes**: Use zendeskTicketNode, slackMessageNode, jiraNode, gmailNode — not apiToolNode — for supported integrations.
8. **Template for Formatting**: Add templateNode before chatOutputNode when the user wants formatted output.
