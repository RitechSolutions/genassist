# Loop Node

The Loop node (`loopNode`) repeats a set of nodes. It is the only way a workflow can run a node more than once: the engine never revisits a node on its own.

## Modes

| Mode | What it does | Typical use |
|---|---|---|
| For each item (`forEach`) | Runs the body once per item of a list | Summarise every ticket, message every recipient |
| Repeat until (`repeatUntil`) | Runs the body until the stop condition holds or the maximum is reached | Draft, review and rewrite until approved |

## Wiring

```
upstream ──input──▶ Loop ──Loop body──▶ first node … last node ──┐
                     ▲  └──Done──▶ what runs after the loop       │
                     └──────────────Loop back─────────────────────┘
```

| Handle | Id | Role |
|---|---|---|
| Input (left) | `input` | What the loop receives |
| Loop body (upper right) | `output_loop` | Starts the nodes that repeat |
| Loop back (bottom) | `input_loop` | The last repeated node connects here; its output is the result of the pass |
| Done (lower right) | `output_done` | Continues once the loop has finished |

Rules, enforced on the canvas and again when the workflow is saved:

- A connection may only close a cycle through a Loop's **Loop back** input.
- Only a node that runs inside the loop can connect to its Loop back input.
- Nodes that run after the loop are connected from **Done** only; a body node cannot feed them directly.
- Nothing that pauses the run for user input can run inside a loop body, because a paused run cannot be resumed mid-loop. That rules out a Human in the Loop node in the body, and for an agent in the body: a **task** or **chat** sub-agent (at any depth), and a tool whose sub-flow reaches a Human in the Loop node. Agents with ordinary tools and **single turn** sub-agents are fine.

Loops can be nested. A nested loop deals with failures in its own body: one it carries on past (`onError: continue`) is not a failure of the outer pass, one that stops it is. A Filter inside the body skips the current item. If nothing is connected to Loop back, the last body node that ran provides the result.

## Configuration

| Field | Key | Notes |
|---|---|---|
| Mode | `mode` | `forEach` (default) or `repeatUntil` |
| Items | `items` | For each item only. A list, usually a variable such as `{{source.tickets}}`. An object iterates as `{key, value}` entries; a whole number N repeats N times (`item` = 0..N-1); plain text is split on lines, or on commas when it is one line; an empty value is an empty list. `true`/`false`, negative and fractional numbers fail the node |
| Batch size | `batchSize` | For each item only, default 1. Items per pass; above 1 the body receives a list in `item`, and Maximum iterations counts batches |
| Maximum iterations | `maxIterations` | Default 100 (For each item) or 5 (Repeat until) |
| Stop when / Repeat until | `stopField`, `stopOperator`, `stopValue`, `stopCaseSensitive` | Checked after every pass, with the same operators as the Filter node. Reads the pass's result (`{{node_outputs.<loop id>.result}}`, inserted by the "the result of the pass" link in the dialog) or any node inside the loop (`{{node_outputs.<node id>.verdict}}`). `{{source…}}` is the Loop's own input, as in every node |
| When a pass fails | `onError` | `stop` (default) ends the loop; `continue` goes on to the next pass |
| Wait between passes | `delaySeconds`, `delayBackoff` | Default 0, at most 60 seconds. Never waits before the first pass. With backoff the wait doubles after every pass, up to 60 seconds |
| Time limit | `timeLimitSeconds` | Default 0 (none). No new pass starts once the loop has run this long, or when the next wait would run past it; a pass already running finishes |
| Results to keep | `collect` | `all` (default), `last` or `none`: what Done receives in `results` |

## What nodes can read

Inside the loop, from the Loop node (`{{source…}}` for the first body node, `{{node_outputs.<loop id>…}}` deeper in):

| Field | Meaning |
|---|---|
| `item` | The current item (For each item), or a list of items when Batch size is above 1 |
| `index` / `iteration` | 0-based / 1-based pass number |
| `total` | Number of passes: items (or batches), or the maximum for Repeat until |
| `is_first` / `is_last` | Position flags |
| `previous` | The result of the last pass that succeeded |
| `input` | What the Loop itself received |
| `result` | This pass's result, available once the pass has run (used by the stop condition) |

After the loop, from Done:

| Field | Meaning |
|---|---|
| `results` | One entry per pass that produced a result, in order. Passes in which a node failed are left out. Trimmed by Results to keep |
| `last` | The last result (empty when Results to keep is None) |
| `count` / `iterations` / `total` / `total_items` | Passes that produced a result, passes run, passes planned, size of the list |
| `skipped` / `failed` | Passes without a result (e.g. stopped by a Filter), passes in which a node failed |
| `errors` | `{index, node_id, node_name, error}` for every body node that failed |
| `stopped_reason` | `completed`, `condition`, `max_iterations`, `error`, `timeout`, `budget` or `no_body` |

## Behaviour and limits

- Passes run one at a time, in order. Body outputs are cleared before each pass, so a node never reads a value left over from the previous one.
- In the variable picker, `item` shows the fields of the first element when Items is a single variable pointing at a list the builder already knows (from a test run or a schema).
- A failing pass ends the loop (or is skipped with `onError: continue`); either way the workflow continues from Done with the failures in `errors`, and the run reports `has_failures`.
- A deactivated Loop skips its body and continues from Done with its input unchanged.
- Server limits (settings): `WORKFLOW_LOOP_MAX_ITERATIONS` (1000 per loop) and `WORKFLOW_LOOP_MAX_TOTAL_ITERATIONS` (5000 per run, across nested loops).
- The run trace keeps the 20 most recent earlier passes of each body node; the latest pass carries `run`, the number of times the node ran, which the Execution view shows as `×N`.

## Implementation

- Engine: `backend/app/modules/workflow/engine/nodes/loop_node.py` drives the iteration and calls `WorkflowEngine.run_subgraph` for each pass; `engine/loops.py` holds the topology helpers and the save-time validation (`WorkflowService._validate_loops`, error key `LOOP_INVALID_TOPOLOGY`).
- Frontend: `nodeTypes/router/loopNode.tsx`, `nodeDialogs/LoopDialog.tsx`, `utils/loopGraph.ts` (canvas rules, shared with the layouts and the variable picker).
- Tests: `backend/tests/unit/workflow/test_loop_node.py`, `test_loop_node_registration.py`; `frontend/tests/views/AIAgents/Workflows/utils/loopGraph.test.ts`.
