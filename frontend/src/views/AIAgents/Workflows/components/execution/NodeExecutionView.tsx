import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Loader2,
  Workflow as WorkflowIcon,
  AlertTriangle,
  Maximize2,
  Minimize2,
  ListOrdered,
  Network,
} from 'lucide-react';
import { cn } from '@/helpers/utils';
import { Workflow } from '@/interfaces/workflow.interface';
import { buildExecutionViewModel, deriveExecutionViewState } from '../../utils/executionView';
import ExecutionSummary from './ExecutionSummary';
import ExecutionGraph from './ExecutionGraph';
import ExecutionTimeline from './ExecutionTimeline';
import NodeDetailPanel from './NodeDetailPanel';

/**
 * The "Execution" view: visualizes what happened with each node of the last test run as a
 * status-colored DAG plus a run-level summary, an execution-order timeline, and a
 * click-to-inspect detail panel. Handles the four interactive states (loading / error / empty /
 * data).
 *
 * The node detail opens as a side panel of the test dialog itself (rendered inside the dialog's
 * DOM, not a separate portal) so scrolling, focus and dismissal all work natively within the
 * dialog's scroll lock. "Expand" grows the graph area to give large graphs more room.
 * See spec FR-1, FR-5..FR-9.
 */
interface NodeExecutionViewProps {
  /** The raw workflow-test response (loosely typed on purpose — the adapter narrows it). */
  response: unknown;
  /** True while a test is running. */
  testing: boolean;
  /** Error string from a failed test request, if any. */
  error: string | null;
  /** The workflow whose structure drives the graph. */
  workflow: Workflow | null;
}

const StateShell: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <div className="flex h-[420px] items-center justify-center rounded-md border border-gray-200 bg-gray-50 p-6 text-center">
    {children}
  </div>
);

const ToolbarButton: React.FC<{
  onClick: () => void;
  active?: boolean;
  label: string;
  children: React.ReactNode;
}> = ({ onClick, active, label, children }) => (
  <button
    type="button"
    onClick={onClick}
    aria-label={label}
    aria-pressed={active}
    title={label}
    className={cn(
      'inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1.5 text-xs font-medium transition-colors',
      active ? 'border-brand-600 bg-brand-600 text-white' : 'border-gray-200 bg-white text-gray-600 hover:bg-gray-50'
    )}
  >
    {children}
  </button>
);

const NodeExecutionView: React.FC<NodeExecutionViewProps> = ({ response, testing, error, workflow }) => {
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [expanded, setExpanded] = useState(false);
  const [showTimeline, setShowTimeline] = useState(false);
  const [graphView, setGraphView] = useState<'executed' | 'full'>('executed');

  const viewState = deriveExecutionViewState(response, testing, error);
  const model = useMemo(() => buildExecutionViewModel(response, workflow), [response, workflow]);
  const selectedNode = selectedNodeId ? (model.byId[selectedNodeId] ?? null) : null;

  const closeDetail = useCallback(() => setSelectedNodeId(null), []);
  const handleSelectNode = useCallback((id: string) => setSelectedNodeId(id), []);

  // Escape closes the detail panel first, then collapses Expand — captured before the parent
  // dialog sees it so those actions don't close the whole dialog.
  useEffect(() => {
    if (!selectedNodeId && !expanded) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key !== 'Escape') return;
      e.preventDefault();
      e.stopPropagation();
      if (selectedNodeId) setSelectedNodeId(null);
      else if (expanded) setExpanded(false);
    };
    window.addEventListener('keydown', onKeyDown, true);
    return () => window.removeEventListener('keydown', onKeyDown, true);
  }, [selectedNodeId, expanded]);

  if (viewState === 'loading') {
    return (
      <StateShell>
        <div className="space-y-2 text-gray-500">
          <Loader2 className="mx-auto h-6 w-6 animate-spin" aria-hidden="true" />
          <div className="text-sm">Running the workflow…</div>
        </div>
      </StateShell>
    );
  }

  if (viewState === 'error') {
    return (
      <StateShell>
        <div className="space-y-2 text-red-600">
          <AlertTriangle className="mx-auto h-6 w-6" aria-hidden="true" />
          <div className="text-sm font-medium">The test run failed</div>
          {error && <div className="text-xs text-red-500">{error}</div>}
        </div>
      </StateShell>
    );
  }

  if (viewState === 'empty') {
    return (
      <StateShell>
        <div className="space-y-2 text-gray-500">
          <WorkflowIcon className="mx-auto h-6 w-6" aria-hidden="true" />
          <div className="text-sm font-medium">No execution yet</div>
          <div className="text-xs">Run a test to see what happened with each node.</div>
        </div>
      </StateShell>
    );
  }

  // data — but the response may still carry no usable node execution data (partial/malformed).
  if (!model.totalNodes) {
    return (
      <StateShell>
        <div className="space-y-2 text-gray-500">
          <WorkflowIcon className="mx-auto h-6 w-6" aria-hidden="true" />
          <div className="text-sm font-medium">No node execution data</div>
          <div className="text-xs">
            This run did not report per-node status. Try the Debug tab for the raw response.
          </div>
        </div>
      </StateShell>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      {/* Toolbar — thin summary strip + view controls on one line */}
      <div className="flex items-center justify-between gap-3">
        <div className="min-w-0 flex-1">
          <ExecutionSummary model={model} />
        </div>
        <div className="flex shrink-0 items-center gap-1.5">
          <ToolbarButton
            onClick={() => setGraphView((v) => (v === 'full' ? 'executed' : 'full'))}
            active={graphView === 'full'}
            label={
              graphView === 'full'
                ? 'Showing the full workflow (click to focus the executed path)'
                : 'Showing the executed path (click to see the full workflow)'
            }
          >
            <Network className="h-4 w-4" />
            {graphView === 'full' ? 'Full' : 'Path'}
          </ToolbarButton>
          <ToolbarButton onClick={() => setShowTimeline((v) => !v)} active={showTimeline} label="Toggle timeline">
            <ListOrdered className="h-4 w-4" />
            Timeline
          </ToolbarButton>
          <ToolbarButton
            onClick={() => setExpanded((v) => !v)}
            label={expanded ? 'Shrink graph (Esc)' : 'Expand graph'}
          >
            {expanded ? <Minimize2 className="h-4 w-4" /> : <Maximize2 className="h-4 w-4" />}
            {expanded ? 'Shrink' : 'Expand'}
          </ToolbarButton>
        </div>
      </div>

      {/* Graph area. The node detail is a side panel of this area (in-dialog), and the timeline
          is a bottom slide-up — both stay within the dialog so they scroll/interact natively. */}
      <div
        className={cn(
          'relative overflow-hidden rounded-md border border-gray-200 transition-[height] duration-200',
          expanded ? 'h-[82vh]' : 'h-[58vh] min-h-[420px]'
        )}
      >
        <ExecutionGraph
          key={graphView}
          workflow={workflow}
          model={model}
          selectedNodeId={selectedNodeId}
          onSelectNode={handleSelectNode}
          graphView={graphView}
        />

        {/* Dim scrim behind the detail panel — click to close. */}
        <div
          className={cn(
            'absolute inset-0 z-10 bg-black/10 transition-opacity duration-200',
            selectedNode ? 'opacity-100' : 'pointer-events-none opacity-0'
          )}
          onClick={closeDetail}
          aria-hidden="true"
        />

        {/* Node detail — a wide side panel of the popup. */}
        <div
          role="dialog"
          aria-label="Node execution details"
          aria-hidden={!selectedNode}
          className={cn(
            'absolute inset-y-0 right-0 z-20 flex w-full max-w-[620px] transform flex-col border-l border-gray-200 bg-white shadow-xl transition-transform duration-200 ease-out sm:w-[62%]',
            selectedNode ? 'translate-x-0' : 'pointer-events-none translate-x-full'
          )}
        >
          <NodeDetailPanel node={selectedNode} onClose={closeDetail} />
        </div>

        {/* Timeline — bottom slide-up. */}
        <div
          className={cn(
            'absolute inset-x-0 bottom-0 z-30 h-[45%] max-h-[280px] transform border-t border-gray-200 bg-white/95 shadow-[0_-4px_12px_rgba(0,0,0,0.06)] backdrop-blur transition-transform duration-200 ease-out',
            showTimeline ? 'translate-y-0' : 'pointer-events-none translate-y-full'
          )}
          aria-hidden={!showTimeline}
        >
          <div className="flex items-center justify-between border-b border-gray-100 px-3 py-1.5 text-xs font-semibold uppercase tracking-wide text-gray-500">
            Execution order
            <button
              type="button"
              onClick={() => setShowTimeline(false)}
              className="rounded px-1.5 py-0.5 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
            >
              Hide
            </button>
          </div>
          <div className="h-[calc(100%-32px)]">
            <ExecutionTimeline model={model} selectedNodeId={selectedNodeId} onSelectNode={handleSelectNode} />
          </div>
        </div>
      </div>
    </div>
  );
};

export default NodeExecutionView;
