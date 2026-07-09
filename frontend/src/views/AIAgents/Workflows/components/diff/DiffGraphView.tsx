import React, { useCallback, useMemo, useState } from 'react';
import ReactFlow, {
  Background,
  Controls,
  Edge,
  MarkerType,
  Node,
  NodeMouseHandler,
  NodeTypes,
  ReactFlowProvider,
} from 'reactflow';
import 'reactflow/dist/style.css';
import { cn } from '@/helpers/utils';
import { ScrollArea } from '@/components/scroll-area';
import { Workflow } from '@/interfaces/workflow.interface';
import { NodeDiff, WorkflowDiff } from '@/interfaces/workflow-diff.interface';
import { computeLayeredLayout } from '../../utils/executionLayout';
import { getNodeLabel } from '../../utils/versionDiff';
import { NodeHandler } from '../../types/nodes';
import { DIFF_STATUS_STYLES } from './diffStatusStyles';
import DiffStatusNode, { DiffStatusNodeData } from './DiffStatusNode';
import FieldChangeRow from './FieldChangeRow';

/**
 * Side-by-side graph presentation of a workflow diff (spec FR-13/FR-14, AC-12). Renders the base
 * and target versions as two read-only, pan/zoomable ReactFlow graphs laid out compactly with
 * `computeLayeredLayout`; every node is coded by its diff status (icon + label + color, never color
 * alone). Selecting a node on either side reveals its field-level changes in a shared detail panel.
 * Mirrors the read-only ReactFlow setup of the Execution view's `ExecutionGraph`.
 */
export interface DiffGraphViewProps {
  diff: WorkflowDiff;
}

const NODE_TYPES: NodeTypes = { diffStatus: DiffStatusNode };
const PRO_OPTIONS = { hideAttribution: true };
const FIT_VIEW_OPTIONS = { padding: 0.2, maxZoom: 1.1, minZoom: 0.2 };
const DEFAULT_EDGE_OPTIONS = {
  type: 'smoothstep',
  markerEnd: { type: MarkerType.ArrowClosed, width: 16, height: 16 },
};

interface DiffGraphPaneProps {
  title: string;
  subtitle: string;
  workflow: Workflow;
  diffById: Map<string, NodeDiff>;
  selectedNodeId: string | null;
  onSelectNode: (nodeId: string) => void;
}

const DiffGraphPane: React.FC<DiffGraphPaneProps> = ({
  title,
  subtitle,
  workflow,
  diffById,
  selectedNodeId,
  onSelectNode,
}) => {
  const sourceNodes = useMemo(() => workflow.nodes ?? [], [workflow.nodes]);
  const sourceEdges = useMemo(() => workflow.edges ?? [], [workflow.edges]);

  const positions = useMemo(
    () =>
      computeLayeredLayout(
        sourceNodes.map((n) => n.id),
        sourceEdges.map((e) => ({ source: e.source, target: e.target }))
      ),
    [sourceNodes, sourceEdges]
  );

  const displayNodes = useMemo<Node<DiffStatusNodeData>[]>(
    () =>
      sourceNodes.map((node) => {
        const data = node.data as { name?: string; handlers?: NodeHandler[] };
        const nodeDiff = diffById.get(node.id);
        return {
          id: node.id,
          type: 'diffStatus',
          position: positions[node.id] ?? node.position ?? { x: 0, y: 0 },
          data: {
            // Label from THIS pane's own node so the base graph shows base-version names and the
            // target graph shows target-version names (diff status still comes from the shared map).
            name: getNodeLabel(node),
            handlers: data?.handlers,
            status: nodeDiff?.status ?? 'unchanged',
            fieldChangeCount: nodeDiff?.fieldChanges.length ?? 0,
            isSelected: selectedNodeId === node.id,
          },
          draggable: false,
          connectable: false,
          selectable: true,
        };
      }),
    [sourceNodes, positions, diffById, selectedNodeId]
  );

  const displayEdges = useMemo<Edge[]>(() => sourceEdges.map((edge) => ({ ...edge, animated: false })), [sourceEdges]);

  const handleNodeClick = useMemo<NodeMouseHandler>(() => (_event, node) => onSelectNode(node.id), [onSelectNode]);

  return (
    <div className="flex min-w-0 flex-1 flex-col">
      <div className="flex items-baseline justify-between gap-2 px-1 pb-1.5">
        <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">{title}</span>
        <span className="truncate text-xs font-medium text-slate-600" title={subtitle}>
          {subtitle}
        </span>
      </div>
      <div className="min-h-0 flex-1 overflow-hidden rounded-lg border border-slate-200 bg-slate-50/60">
        {displayNodes.length === 0 ? (
          <div className="flex h-full items-center justify-center p-4 text-center text-xs text-slate-500">
            This version has no nodes.
          </div>
        ) : (
          <ReactFlowProvider>
            <ReactFlow
              nodes={displayNodes}
              edges={displayEdges}
              nodeTypes={NODE_TYPES}
              defaultEdgeOptions={DEFAULT_EDGE_OPTIONS}
              onNodeClick={handleNodeClick}
              nodesDraggable={false}
              nodesConnectable={false}
              elementsSelectable
              minZoom={0.1}
              fitView
              fitViewOptions={FIT_VIEW_OPTIONS}
              proOptions={PRO_OPTIONS}
              onlyRenderVisibleElements
            >
              <Background />
              <Controls showInteractive={false} />
            </ReactFlow>
          </ReactFlowProvider>
        )}
      </div>
    </div>
  );
};

const DiffGraphView: React.FC<DiffGraphViewProps> = ({ diff }) => {
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);

  const diffById = useMemo(() => {
    const map = new Map<string, NodeDiff>();
    for (const node of diff.nodes) map.set(node.id, node);
    return map;
  }, [diff.nodes]);

  const selectedNode = selectedNodeId ? diffById.get(selectedNodeId) : undefined;

  const versionLabel = (workflow: Workflow): string =>
    `${workflow.name}${workflow.version ? ` · v${workflow.version}` : ''}`;

  const selectedStyle = selectedNode ? DIFF_STATUS_STYLES[selectedNode.status] : null;

  return (
    <div className="flex h-full flex-col gap-3">
      <div className="flex min-h-0 flex-1 gap-3">
        <DiffGraphPane
          title="Base (older)"
          subtitle={versionLabel(diff.base)}
          workflow={diff.base}
          diffById={diffById}
          selectedNodeId={selectedNodeId}
          onSelectNode={setSelectedNodeId}
        />
        <DiffGraphPane
          title="Target (newer)"
          subtitle={versionLabel(diff.target)}
          workflow={diff.target}
          diffById={diffById}
          selectedNodeId={selectedNodeId}
          onSelectNode={setSelectedNodeId}
        />
      </div>

      {/* Shared detail panel: reveals the selected node's field-level changes (FR-13). */}
      <div className="h-40 shrink-0 overflow-hidden rounded-lg border border-slate-200 bg-white">
        {selectedNode && selectedStyle ? (
          <div className="flex h-full flex-col">
            <div className="flex items-center gap-2 border-b border-slate-100 bg-slate-50/60 px-3 py-2">
              <span className={cn('h-2 w-2 shrink-0 rounded-full', selectedStyle.dotClass)} aria-hidden="true" />
              <span className="truncate text-sm font-medium text-slate-700">{selectedNode.label}</span>
              <span
                className={cn(
                  'inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-[10px] font-medium',
                  selectedStyle.chipClass
                )}
              >
                <selectedStyle.Icon className="h-3 w-3" aria-hidden="true" />
                {selectedStyle.label}
              </span>
            </div>
            <ScrollArea className="flex-1 p-3">
              {selectedNode.fieldChanges.length > 0 ? (
                <div className="space-y-2">
                  {selectedNode.fieldChanges.map((change) => (
                    <FieldChangeRow key={change.key} change={change} />
                  ))}
                </div>
              ) : (
                <p className="text-xs text-slate-500">
                  {selectedNode.status === 'unchanged'
                    ? 'This node is unchanged between the two versions.'
                    : selectedNode.status === 'added'
                      ? 'This node was added in the target version.'
                      : 'This node was removed from the base version.'}
                </p>
              )}
            </ScrollArea>
          </div>
        ) : (
          <div className="flex h-full items-center justify-center px-3 text-center text-xs text-slate-500">
            Select a node in either graph to see its changes.
          </div>
        )}
      </div>
    </div>
  );
};

export default DiffGraphView;
