# Node Execution Visualization ("Execution" tab)

## Overview

When you test a workflow from the builder (**Test Workflow: Current Graph** dialog), the
response already carries rich per-node telemetry (`nodeExecutionStatus`) alongside run-level
fields (`total_steps`, `current_step`, `execution_start_time`). Until now that information was
only visible as a deeply-nested, collapsed JSON blob under the **Debug** view.

The **Execution** tab adds a human-readable, visual answer to *"what actually happened with each
node?"* It renders the workflow as a status-colored graph, a run-level summary, and a
click-to-inspect detail panel — no JSON spelunking required.

## Why it matters

- **Diagnose runs at a glance** — see which nodes ran, in what order, which succeeded, failed,
  or were skipped, and how long each took.
- **Find the bottleneck** — the slowest node is highlighted and per-node durations are shown.
- **Debug a specific step** — click any node to inspect its input, output, error, and timing.

## How to use

1. Open a workflow in the builder and click **Test** (or the test-graph action) to open the
   **Test Workflow** dialog.
2. Enter a message / inputs and press **Test** to run the workflow.
3. Click the **Execution** button (next to **Debug**) to switch to the visualization.
   - **Response** — the human-facing answer (unchanged).
   - **Debug** — the raw JSON response (unchanged).
   - **Execution** — the new visual view.
4. In the Execution view:
   - The **summary** row shows total nodes, counts by status, total steps, overall duration,
     and the slowest node.
   - The **graph** draws the DAG with each node colored + labeled by its status and numbered by
     execution order. By default it shows the **executed path** — only the nodes that ran,
     re-laid out compactly so the run is readable no matter how spread out the original canvas
     is. The **Path / Full** toggle switches to the **full workflow** in its own designed
     positions (framed on the executed nodes). Both are pannable / zoomable.
   - **Click a node** to open the **detail side panel** — a wide panel of the dialog that slides
     in from the right with the node's status, duration, input, output, and any error. Click the
     scrim, the ✕, or press **Esc** to close it.
   - **Expand** (top-right) grows the graph area to give large graphs more room; **Shrink** or
     **Esc** returns it. The run data is preserved.
   - **Timeline** (top-right) slides up an execution-order list with per-node duration bars, so
     you can read the sequence and spot the bottleneck at a glance. Clicking a row selects the
     node.

### States

The tab handles all four states:

- **Empty** — no test has been run yet ("Run a test to see what happened with each node").
- **Loading** — a test is currently running.
- **Error** — the test request failed (the error is surfaced).
- **Data** — a completed (or paused) run; the graph + summary + details render.

If a run reports no per-node data (or the payload is malformed), the tab degrades gracefully to
a partial/empty message instead of crashing, and points you to the Debug tab for the raw
response.

## End-to-end flow

```
  Test Workflow dialog
        │  user runs a test
        ▼
  POST genagent/workflow/test  ──►  { status, output, state: { nodeExecutionStatus, … } }
        │  (response held in the dialog; no extra fetch)
        ▼
  buildExecutionViewModel(response, workflow)   ← pure, defensive adapter
        │   • reads state.nodeExecutionStatus (falls back to top level)
        │   • maps backend status  "success"→completed, "failed", "running"
        │   • time_taken → duration; recomputes counts / slowest / overall duration
        │   • collapses archived re-run keys ("{id}_0", …)
        │   • never throws on partial/malformed input
        ▼
  ExecutionViewModel  →  Summary + read-only reactflow DAG + Node detail panel
```

## Design notes

- **Frontend-only.** No backend, API, or database changes — the Execution tab is a new view over
  the data the test endpoint already returns.
- **Wire-format adapter.** The backend per-node payload (`type/name/status/startTime/endTime/
  time_taken/input/output/error`, keyed by node id, nested under `response.state`) does **not**
  match the legacy `NodeExecutionStatus` TypeScript interface. A single pure adapter
  (`utils/executionView.ts`) normalizes it into a typed `ExecutionViewModel`; that adapter is the
  unit-tested seam. The legacy interfaces are marked `@deprecated`.
- **Status is never color-only.** Every status pairs a color with an icon and a text label
  (completed ✓, failed ✕, running ⟳, skipped ⊖, not-run ○) for accessibility.
- **Reuses the builder's graph.** The DAG uses the same reactflow v11 setup as the workflow
  editor but read-only, with one lightweight status node for every type. Edge handles are
  rendered from each node's `handlers` config (via the shared `HandlersRenderer`) so
  multi-handle / router nodes keep all their edges.
- **Executed-path focus by default.** The point of the view is "what happened", so it defaults
  to just the nodes that ran, re-laid out with a tiny dependency-free layered layout
  (`utils/executionLayout.ts`) — compact and readable even when the source workflow is huge and
  sparse (fitting the whole canvas would shrink nodes to specks). A **Path / Full** toggle shows
  the entire workflow in its designed positions, still framed on the executed nodes. The layout
  degrades gracefully on cycles and isolated nodes.
- **Everything stays inside the dialog.** Test runs are ephemeral (held in the modal, not
  persisted), so rather than a separate page or a portalled overlay, the node detail is a side
  panel *of the dialog itself* and Expand grows the graph in place. Keeping it within the
  dialog's DOM means scrolling, focus, and dismissal all work natively (a portalled overlay
  fights the dialog's scroll-lock / focus-trap) — and the in-memory run is never lost.
- **Recomputes metrics.** The backend's `performanceMetrics` is stale on failed runs (it is only
  updated on successful completion), so the view derives counts, slowest node, and durations from
  the raw per-node timings instead.

## Related code

- View selector + integration: `frontend/src/views/AIAgents/Workflows/components/WorkflowTestDialog.tsx`
- Adapter (pure, tested): `frontend/src/views/AIAgents/Workflows/utils/executionView.ts`
- Components: `frontend/src/views/AIAgents/Workflows/components/execution/`
  (`NodeExecutionView`, `ExecutionSummary`, `ExecutionGraph`, `ExecutionStatusNode`,
  `NodeDetailPanel`, `statusStyles`)
- Types: `frontend/src/interfaces/workflow-execution.interface.ts`
  (`RawNodeExecutionEntry`, `NodeExecutionView`, `ExecutionViewModel`, `ExecutionViewState`)
- Unit tests: `frontend/src/views/AIAgents/Workflows/utils/executionView.test.ts`
