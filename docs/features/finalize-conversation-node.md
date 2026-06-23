# End Conversation Node

The **End Conversation** node lets a workflow builder explicitly finalize the active
conversation at a chosen point in a workflow — closing it out with exactly the same outcome
as the platform's existing "finalize conversation" behavior.

## Why it matters

Until now, a conversation could only be finalized indirectly through backend logic (for
example, the stale-conversation cleanup job or the Zendesk sync). Builders had no first-class
way to say "the user's issue is resolved — close this conversation now" from inside a
workflow. The End Conversation node gives builders that explicit control while guaranteeing
the close-out behaves identically to every other finalize path (status change, KPI analysis,
operator statistics, optional Zendesk store).

## How to use / enable

1. Open the **Workflow builder** (AI Agents → Workflows).
2. From the node palette, drag the **End Conversation** node onto the canvas (it sits with the
   chat input/output nodes).
3. Wire your flow into the node's **input** handle. Because it is a pass-through node, you can
   also wire its **output** handle to any follow-up nodes — finalizing does not stop the run.
4. Save the workflow. The node reloads cleanly on reopen, like any other node.

No configuration is required: the node always finalizes the conversation the workflow is
currently running for, and always uses the system default analyst.

## What it does (behavior)

When execution reaches the node, it resolves the current conversation from the workflow run's
context and calls the canonical finalize action. The same side-effects as any other finalize
occur: conversation status becomes `finalized`, a conversation analysis is produced, operator
statistics are updated, and (when enabled) the result is stored in Zendesk.

| Situation | Node behavior |
|-----------|---------------|
| Active conversation reached | Conversation is **finalized**; node returns `success`. |
| Conversation already finalized | **Handled no-op** — node returns `skipped`, the run is **not** faulted. |
| No conversation resolvable from context (e.g. a builder preview/test run) | **Handled no-op** — node returns `skipped`, the run continues. |
| Conversation has no analyzable messages | **Surfaced as an error** (consistent with the canonical finalize action). |
| Downstream nodes wired after it | Still execute — the node does **not** halt the run. |

## What it does not do / limitations

- It does **not** change or extend the existing finalize logic or its analytics — it reuses
  them, so behavior stays in sync automatically.
- It does **not** halt the workflow run; it performs finalization as a side-effect only.
- It does **not** expose an analyst selector — finalization always uses the system default
  analyst.
- It does **not** let you target an arbitrary conversation by id; it always acts on the
  conversation the workflow is running for.

## End-to-end flow

```
Workflow run (carries the conversation's thread_id)
        │
        ▼
End Conversation node ── resolves conversation_id from thread_id
        │
        ▼
ConversationService.finalize_in_progress_conversation(conversation_id=…)
        │
        ├─ status → FINALIZED
        ├─ KPI / conversation analysis produced
        ├─ operator statistics updated
        └─ (optional) stored in Zendesk
        │
        ▼
Run continues to any downstream nodes (pass-through)
```

## Under the hood (optional)

- **Backend node:** `backend/app/modules/workflow/engine/nodes/finalize_conversation_node.py`
  (`FinalizeConversationNode`, type id `finalizeConversationNode`). It owns no business logic —
  it resolves the conversation id from `self.state.thread_id`, calls
  `ConversationService.finalize_in_progress_conversation(...)`, and maps
  `CONVERSATION_FINALIZED` / `CONVERSATION_NOT_FOUND` to a no-op and
  `EMPTY_MESSAGES_FOR_CONVERSATION` to a surfaced error.
- **Registration:** engine registry in `workflow_engine.py`; dialog/handler/label schemas in
  `backend/app/schemas/dynamic_form_schemas/nodes/__init__.py`; frontend definition + component
  in `frontend/src/views/AIAgents/Workflows/nodeTypes/chat/`.
- **Tests:** `backend/tests/unit/workflow/test_finalize_conversation_node.py` and
  `test_finalize_conversation_node_registration.py`.

## Related

- Spec: `specs/001-63996-finalize-conversation-node/spec.md`
- Azure work item: [#63996](https://dev.azure.com/Ritech/GenAssist/_workitems/edit/63996)
