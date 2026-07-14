import React, { useCallback, useEffect, useMemo, useState } from 'react';
import ReactFlow, {
  Background,
  Controls,
  Panel,
  Edge,
  MarkerType,
  Node,
  NodeMouseHandler,
  NodeTypes,
  ReactFlowInstance,
  ReactFlowProvider,
  useReactFlow,
} from 'reactflow';
import 'reactflow/dist/style.css';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { cn } from '@/helpers/utils';
import { ExecutionViewModel } from '@/interfaces/workflow-execution.interface';
import { Workflow } from '@/interfaces/workflow.interface';
import { formatDuration } from '../../utils/executionView';
import { computeLayeredLayout } from '../../utils/executionLayout';
import { STATUS_STYLES } from './statusStyles';
import ExecutionStatusNode, { ExecutionStatusNodeData } from './ExecutionStatusNode';

/**
 * Read-only DAG of the workflow, each node overlaid with its execution status. Reuses the same
 * reactflow v11 setup as the builder but non-interactive and with one lightweight status node for
 * every type. Positions are recomputed with a compact layered layout (not the editor's sparse
 * coordinates) so the graph stays legible and fitView doesn't shrink nodes to specks. When the
 * workflow has no edges we fall back to an ordered status list. See spec FR-5 / FR-9 / AC-9.
 */
interface ExecutionGraphProps {
  workflow: Workflow | null | undefined;
  model: ExecutionViewModel;
  selectedNodeId: string | null;
  onSelectNode: (nodeId: string) => void;
  /**
   * 'executed' (default) shows only the nodes that ran, re-laid out compactly so the run is
   * readable regardless of how spread out the original canvas is. 'full' shows every node in the
   * tested workflow's own designed positions (dimming the ones that did not run).
   */
  graphView?: 'executed' | 'full';
}

// Static so reactflow doesn't warn / remount nodes on every render.
const NODE_TYPES: NodeTypes = { executionStatus: ExecutionStatusNode };
const PRO_OPTIONS = { hideAttribution: true };
const FIT_VIEW_OPTIONS = { padding: 0.2, maxZoom: 1.1, minZoom: 0.2 };
const DEFAULT_EDGE_OPTIONS = {
  type: 'smoothstep',
  markerEnd: { type: MarkerType.ArrowClosed, width: 16, height: 16 },
};

const OrderedFallbackList: React.FC<{
  model: ExecutionViewModel;
  selectedNodeId: string | null;
  onSelectNode: (nodeId: string) => void;
}> = ({ model, selectedNodeId, onSelectNode }) => (
  <div className="h-full space-y-1 overflow-y-auto p-2">
    {model.nodes.map((node) => {
      const style = STATUS_STYLES[node.status] ?? STATUS_STYLES.pending;
      const { Icon } = style;
      return (
        <button
          key={node.nodeId}
          type="button"
          onClick={() => onSelectNode(node.nodeId)}
          className={cn(
            'flex w-full items-center gap-2 rounded-md border px-2 py-1.5 text-left text-sm',
            style.nodeClass,
            selectedNodeId === node.nodeId && 'ring-2 ring-brand-600 ring-offset-1'
          )}
        >
          <span className="w-5 text-xs tabular-nums text-gray-400">{(node.order ?? 0) + 1}</span>
          <Icon
            className={cn('h-4 w-4 shrink-0', style.accentClass, style.spin && 'animate-spin')}
            aria-hidden="true"
          />
          <span className="flex-1 truncate font-medium text-gray-800">{node.name}</span>
          <span className="text-xs tabular-nums text-gray-500">{formatDuration(node.durationMs)}</span>
        </button>
      );
    })}
  </div>
);

/**
 * Bottom-left path stepper: walks the executed nodes in run order (1 → 2 → 3 …), centering and
 * zooming the viewport onto each one. Rendered inside <ReactFlow> so it can drive the viewport via
 * useReactFlow; sits just to the right of the zoom controls.
 */
const PathStepper: React.FC<{ orderedNodeIds: string[] }> = ({ orderedNodeIds }) => {
  const reactFlow = useReactFlow();
  const [index, setIndex] = useState(-1);
  const total = orderedNodeIds.length;

  // A fresh run swaps the node list — restart the walk.
  useEffect(() => setIndex(-1), [orderedNodeIds]);

  const focusNode = useCallback(
    (nextIndex: number) => {
      const id = orderedNodeIds[nextIndex];
      const node = id ? reactFlow.getNode(id) : undefined;
      if (!node) return;
      // Frame just this node so it lands centered and zoomed in.
      reactFlow.fitView({ nodes: [node], padding: 0.3, minZoom: 0.4, maxZoom: 1.5, duration: 400 });
      setIndex(nextIndex);
    },
    [orderedNodeIds, reactFlow]
  );

  if (total < 2) return null;

  const atStart = index <= 0;
  const atEnd = index >= total - 1;

  return (
    <Panel position="bottom-right">
      <div className="flex items-center gap-0.5 rounded-full border border-gray-200 bg-white px-1 shadow-[0_0_2px_1px_rgba(0,0,0,0.08)]">
        <button
          type="button"
          onClick={() => focusNode(index < 0 ? 0 : index - 1)}
          disabled={atStart}
          title="Previous node"
          aria-label="Previous node"
          className="flex h-8 w-8 items-center justify-center rounded-full text-gray-700 transition-colors hover:bg-gray-100 disabled:opacity-40 disabled:hover:bg-transparent"
        >
          <ChevronLeft className="h-3.5 w-3.5" />
        </button>
        <span className="min-w-[2.75rem] select-none text-center text-xs font-medium tabular-nums text-gray-600">
          {index < 0 ? '–' : index + 1}/{total}
        </span>
        <button
          type="button"
          onClick={() => focusNode(index < 0 ? 0 : index + 1)}
          disabled={atEnd}
          title="Next node"
          aria-label="Next node"
          className="flex h-8 w-8 items-center justify-center rounded-full text-gray-700 transition-colors hover:bg-gray-100 disabled:opacity-40 disabled:hover:bg-transparent"
        >
          <ChevronRight className="h-3.5 w-3.5" />
        </button>
      </div>
    </Panel>
  );
};

const ExecutionGraph: React.FC<ExecutionGraphProps> = ({
  workflow,
  model,
  selectedNodeId,
  onSelectNode,
  graphView = 'executed',
}) => {
  const hasGraph = !!(workflow?.nodes?.length && workflow?.edges?.length);

  // The set of nodes that actually ran (present in the execution status map).
  const executedIds = useMemo(() => new Set(Object.keys(model.byId)), [model]);

  // Which nodes/edges to render: the executed subgraph, or the full workflow.
  const { sourceNodes, sourceEdges } = useMemo(() => {
    const allNodes = workflow?.nodes ?? [];
    const allEdges = workflow?.edges ?? [];
    if (graphView === 'full') return { sourceNodes: allNodes, sourceEdges: allEdges };
    return {
      sourceNodes: allNodes.filter((n) => executedIds.has(n.id)),
      sourceEdges: allEdges.filter((e) => executedIds.has(e.source) && executedIds.has(e.target)),
    };
  }, [workflow?.nodes, workflow?.edges, graphView, executedIds]);

  // Executed view: recompute a compact layered layout (small subset → clean + readable).
  // Full view: keep the workflow's own designed positions.
  const positions = useMemo(() => {
    if (graphView === 'full') return {};
    return computeLayeredLayout(
      sourceNodes.map((n) => n.id),
      sourceEdges.map((e) => ({ source: e.source, target: e.target }))
    );
  }, [graphView, sourceNodes, sourceEdges]);

  const displayNodes = useMemo<Node<ExecutionStatusNodeData>[]>(
    () =>
      sourceNodes.map((node) => {
        const exec = model.byId[node.id];
        const data = node.data as { name?: string; handlers?: ExecutionStatusNodeData['handlers'] };
        return {
          id: node.id,
          type: 'executionStatus',
          position: positions[node.id] ?? node.position ?? { x: 0, y: 0 },
          data: {
            name: exec?.name ?? data?.name ?? node.id,
            handlers: data?.handlers,
            status: exec?.status ?? 'pending',
            durationMs: exec?.durationMs,
            order: exec?.order,
            isSlowest: !!model.slowestNodeId && model.slowestNodeId === node.id,
            isSelected: selectedNodeId === node.id,
          },
          draggable: false,
          connectable: false,
          selectable: true,
        };
      }),
    [sourceNodes, positions, model, selectedNodeId]
  );

  const displayEdges = useMemo<Edge[]>(() => sourceEdges.map((edge) => ({ ...edge, animated: false })), [sourceEdges]);

  // Executed nodes in run order (1 → 2 → 3 …) for the bottom-right path stepper.
  const orderedNodeIds = useMemo(
    () =>
      [...model.nodes]
        .sort((a, b) => (a.order ?? 0) - (b.order ?? 0))
        .map((n) => n.nodeId),
    [model.nodes]
  );

  const handleNodeClick = useMemo<NodeMouseHandler>(() => (_event, node) => onSelectNode(node.id), [onSelectNode]);

  // In the full view, frame the executed nodes (not the whole sparse canvas) so the run is
  // still readable; in the executed view every node ran, so fit them all.
  const handleInit = useCallback(
    (instance: ReactFlowInstance) => {
      const executed = displayNodes.filter((n) => executedIds.has(n.id));
      const toFit = executed.length ? executed : displayNodes;
      requestAnimationFrame(() => {
        instance.fitView({ padding: 0.2, minZoom: 0.2, maxZoom: 1.4, duration: 0, nodes: toFit });
      });
    },
    [displayNodes, executedIds]
  );

  if (!hasGraph) {
    if (!model.nodes.length) {
      return (
        <div className="flex h-full items-center justify-center rounded-md border border-dashed border-gray-200 text-sm text-gray-500">
          No node execution data to display.
        </div>
      );
    }
    return (
      <div className="h-full rounded-md border border-gray-200 bg-white">
        <OrderedFallbackList model={model} selectedNodeId={selectedNodeId} onSelectNode={onSelectNode} />
      </div>
    );
  }

  return (
    <div className="h-full overflow-hidden rounded-md border border-gray-200 bg-gray-50">
      <ReactFlowProvider>
        <ReactFlow
          nodes={displayNodes}
          edges={displayEdges}
          nodeTypes={NODE_TYPES}
          defaultEdgeOptions={DEFAULT_EDGE_OPTIONS}
          onNodeClick={handleNodeClick}
          onInit={handleInit}
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
          <PathStepper orderedNodeIds={orderedNodeIds} />
        </ReactFlow>
      </ReactFlowProvider>
    </div>
  );
};

export default ExecutionGraph;
