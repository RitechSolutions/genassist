# User Input Node

The **User Input Node** pauses a running workflow to collect structured data from the end user via a dynamic form, then resumes execution with the submitted values available to all downstream nodes.

## How It Works

```
User sends message
  → engine runs nodes in sequence
  → hits userInputNode
  → engine pauses, saves state to Redis, sends form to chat
  → user fills and submits the form
  → engine resumes from where it paused, with submitted values as node output
  → downstream nodes access values via {{node_outputs.nodeId.fieldName}}
```

On subsequent conversations in the same thread, the node returns the previously submitted data from memory (skips the form).

## Supported Field Types

| Type | Renders As | Value Type |
|------|-----------|------------|
| `text` | Text input | `string` |
| `number` | Number input | `number` |
| `select` | Dropdown (requires `options`) | `string` |
| `boolean` | Checkbox | `boolean` |
| `date` | Date picker | `string` (YYYY-MM-DD) |

## Configuring in the Workflow Builder

1. Drag the **User Input** node from the **IO** category onto the canvas
2. Connect it between any two nodes (it has one input handle and one output handle)
3. Click the settings gear icon to open the configuration panel
4. Set the **Form Message** (text shown above the form to the user)
5. Click **Add Field** to configure each form field:
   - **Field Name (key)**: The variable name used in downstream references (e.g. `location`)
   - **Label**: What the user sees (e.g. "Your Location")
   - **Type**: One of the 5 types above
   - **Required**: Whether the field must be filled before submitting
   - **Placeholder**: Hint text inside the input
   - **Description**: Help text shown below the label
   - For `select` type: add value/label pairs for the dropdown options
6. Click **Save Changes**

## Accessing Submitted Values Downstream

Once the user submits the form, the values are available as the node's output. Use the standard template syntax in any downstream node:

```
{{node_outputs.<userInputNodeId>.<fieldName>}}
```

For example, if the node ID is `node_abc123` and it has a field named `location`:

```
{{node_outputs.node_abc123.location}}
```

## Example Workflow

```
Chat Input → User Input → Language Model → Chat Output
```

**User Input node config:**
- Message: "Please tell us about yourself:"
- Fields:
  - `location` (text, required) — "Your City"
  - `language` (select, required) — options: English, Albanian, Italian
  - `age` (number) — "Your Age"

**Language Model system prompt:**
```
The user is located in {{node_outputs.node_abc123.location}}
and prefers {{node_outputs.node_abc123.language}}.
```

**What happens:**
1. User sends "Hello"
2. Workflow starts, reaches the User Input node, pauses
3. A form appears in the chat with the 3 fields
4. User fills in "Tirana", selects "Albanian", enters "25", clicks Submit
5. Workflow resumes — the LLM receives the values in its system prompt
6. Chat Output sends the LLM's response back to the user
7. On the next message in the same thread, the form is skipped (cached)

## Where the Form Renders

- **Client chat widget** (`plugins/react/`): An interactive form with inputs, validation, and a submit button. Uses inline styles (no external UI library). After submission, the form locks and shows "Submitted".
- **Admin dashboard** (`frontend/`): A read-only card showing the form message and field names as badges. The admin sees what was requested; the user's response appears as the next message in the transcript.

## Testing

- **Test Node** (single node): Click "Test Node" in the settings panel. Returns sample output values based on your configured fields (e.g. `{"location": "Sample text", "age": 42}`).
- **Test Workflow** (full workflow): Run the workflow test from the builder. The User Input node returns sample data so the full pipeline can be validated end-to-end without pausing.

## Technical Details

### Backend Files

| File | Purpose |
|------|---------|
| `engine/nodes/user_input_node.py` | Node class — pause/resume/cache/test logic |
| `engine/exceptions.py` | `WorkflowPausedException` — signals the engine to pause |
| `engine/workflow_state.py` | State serialization for Redis persistence |
| `engine/workflow_engine.py` | `execute_from_node` catches pause, `resume_from_pause` restores and continues |
| `modules/workflow/registry.py` | Detects `user_input_from_form` in metadata to trigger resume |
| `use_cases/chat_as_client_use_case.py` | Creates `form_request` transcript message on pause |
| `schemas/dynamic_form_schemas/nodes/user_input_schema.py` | Empty schema (config handled by custom frontend UI) |

### Frontend Files

| File | Purpose |
|------|---------|
| `nodeTypes/io/userInputNode.tsx` | Workflow builder node (read-only card with settings button) |
| `nodeTypes/io/definitions.ts` | Node type definition (category: `io`, icon: `ClipboardList`) |
| `nodeDialogs/UserInputDialog.tsx` | Settings panel with field editor dialog |
| `ConversationEntryWrapper.tsx` | Admin dashboard — read-only form request display |

### Client Widget Files

| File | Purpose |
|------|---------|
| `plugins/react/src/components/DynamicFormMessage.tsx` | Interactive form component (inline styles) |
| `plugins/react/src/components/GenAgentChat.tsx` | Detects `form_request` messages, renders form, handles submit |

### Message Format

The form is sent as a transcript message with `type: "form_request"` and the schema as JSON in the `text` field:

```json
{
  "type": "form_request",
  "speaker": "agent",
  "text": "{\"message\":\"Please tell us about yourself:\",\"fields\":[{\"name\":\"location\",\"type\":\"text\",\"label\":\"Your City\",\"required\":true}],\"node_id\":\"node_abc123\"}"
}
```

### Redis State

Paused workflow state is stored at:
```
tenant:{tenant_id}:conversation:{thread_id}:paused_workflow
```
TTL: 24 hours. Cleared automatically on resume.

Cached user input (per node) is stored via the conversation memory metadata system under the key `user_input:{node_id}`.

### Limitations

- **No parallel branches**: The User Input node should not be placed inside parallel branches (after a Router node's split). Place it before or after parallel sections.
- **One pause at a time**: If multiple User Input nodes exist in sequence, they pause one at a time — the user fills each form before the next one appears.
- **24-hour expiry**: If the user doesn't submit the form within 24 hours, the paused state expires and the workflow must be restarted.
