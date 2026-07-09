import React from 'react';
import { NodeProps } from 'reactflow';
import { cn } from '@/helpers/utils';
import { ExecutionNodeStatus } from '@/interfaces/workflow-execution.interface';
import { NodeData, NodeHandler } from '../../types/nodes';
import { HandlersRenderer } from '../custom/HandleTooltip';
import { formatDuration } from '../../utils/executionView';
import { STATUS_STYLES } from './statusStyles';

/**
 * Read-only reactflow node used exclusively by the Execution view. It renders an execution-order
 * badge, the node name, a status badge (icon + label + color), and duration. Edge handles are
 * rendered from `data.handlers` via the existing `HandlersRenderer`, so multi-handle/router nodes
 * keep every edge (their `sourceHandle`/`targetHandle` ids resolve). See spec FR-3 / FR-5.
 */
export interface ExecutionStatusNodeData {
  name: string;
  handlers?: NodeHandler[];
  status: ExecutionNodeStatus;
  durationMs?: number;
  order?: number;
  isSlowest?: boolean;
  isSelected?: boolean;
}

const ExecutionStatusNodeComponent: React.FC<NodeProps<ExecutionStatusNodeData>> = ({ id, data }) => {
  const style = STATUS_STYLES[data.status] ?? STATUS_STYLES.pending;
  const { Icon } = style;

  return (
    <div
      className={cn(
        'relative w-[210px] rounded-lg border bg-white px-3 py-2 shadow-sm transition-shadow',
        style.nodeClass,
        data.isSelected ? 'ring-2 ring-brand-600 ring-offset-2 shadow-md' : 'hover:shadow-md'
      )}
    >
      {/* Edge handles driven by the node's own handler config (reused renderer). */}
      <HandlersRenderer id={id} data={data as unknown as NodeData} />

      {/* Execution-order badge */}
      {data.order !== undefined && (
        <span
          className="absolute -left-2 -top-2 flex h-5 min-w-[20px] items-center justify-center rounded-full border border-gray-300 bg-white px-1 text-[10px] font-semibold tabular-nums text-gray-600 shadow-sm"
          aria-label={`Step ${data.order + 1}`}
        >
          {data.order + 1}
        </span>
      )}
      {data.isSlowest && (
        <span
          className="absolute -right-2 -top-2 rounded-full bg-amber-500 px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wide text-white shadow-sm"
          title="Slowest node"
        >
          Slowest
        </span>
      )}

      <div className="flex items-center gap-1.5">
        <Icon className={cn('h-4 w-4 shrink-0', style.accentClass, style.spin && 'animate-spin')} aria-hidden="true" />
        <span className="truncate text-sm font-medium text-gray-800" title={data.name}>
          {data.name}
        </span>
      </div>

      <div className="mt-1.5 flex items-center justify-between gap-2">
        <span
          className={cn(
            'inline-flex items-center rounded-full border px-1.5 py-0.5 text-[10px] font-medium',
            style.chipClass
          )}
        >
          {style.label}
        </span>
        {data.durationMs !== undefined && (
          <span
            className={cn('text-[10px] tabular-nums text-gray-500', data.isSlowest && 'font-semibold text-amber-600')}
          >
            {formatDuration(data.durationMs)}
          </span>
        )}
      </div>
    </div>
  );
};

export const ExecutionStatusNode = React.memo(ExecutionStatusNodeComponent);
export default ExecutionStatusNode;
