import React from 'react';
import { cn } from '@/helpers/utils';
import { ExecutionViewModel } from '@/interfaces/workflow-execution.interface';
import { formatDuration } from '../../utils/executionView';
import { STATUS_STYLES } from './statusStyles';

/**
 * Execution order + per-node duration bars. Rows are ordered by execution start, the bar length
 * is proportional to the node's duration (so the bottleneck is obvious), and the slowest node is
 * emphasized. Clicking a row selects that node. See spec FR-5 / FR-6 / AC-3.
 */
interface ExecutionTimelineProps {
  model: ExecutionViewModel;
  selectedNodeId: string | null;
  onSelectNode: (nodeId: string) => void;
}

const BAR_STATUS_CLASS: Record<string, string> = {
  completed: 'bg-green-400',
  failed: 'bg-red-400',
  running: 'bg-blue-400',
  skipped: 'bg-gray-300',
  pending: 'bg-gray-200',
};

const ExecutionTimeline: React.FC<ExecutionTimelineProps> = ({ model, selectedNodeId, onSelectNode }) => {
  const maxDuration = Math.max(1, ...model.nodes.map((n) => n.durationMs ?? 0));

  return (
    <div className="h-full overflow-y-auto p-1">
      <ul className="space-y-0.5">
        {model.nodes.map((node) => {
          const style = STATUS_STYLES[node.status] ?? STATUS_STYLES.pending;
          const { Icon } = style;
          const pct = node.durationMs ? Math.max(2, (node.durationMs / maxDuration) * 100) : 0;
          const isSelected = selectedNodeId === node.nodeId;
          return (
            <li key={node.nodeId}>
              <button
                type="button"
                onClick={() => onSelectNode(node.nodeId)}
                className={cn(
                  'flex w-full items-center gap-2 rounded-md px-2 py-1 text-left hover:bg-gray-50',
                  isSelected && 'bg-brand-50 ring-1 ring-brand-200'
                )}
              >
                <span className="w-5 shrink-0 text-right text-[11px] tabular-nums text-gray-400">
                  {(node.order ?? 0) + 1}
                </span>
                <Icon
                  className={cn('h-3.5 w-3.5 shrink-0', style.accentClass, style.spin && 'animate-spin')}
                  aria-hidden="true"
                />
                <span className="w-32 shrink-0 truncate text-xs font-medium text-gray-700" title={node.name}>
                  {node.name}
                </span>
                <span className="relative h-3 flex-1 overflow-hidden rounded-full bg-gray-100">
                  <span
                    className={cn(
                      'absolute inset-y-0 left-0 rounded-full',
                      BAR_STATUS_CLASS[node.status] ?? 'bg-gray-300',
                      node.nodeId === model.slowestNodeId && 'ring-1 ring-amber-500'
                    )}
                    style={{ width: `${pct}%` }}
                  />
                </span>
                <span className="w-16 shrink-0 text-right text-[11px] tabular-nums text-gray-500">
                  {formatDuration(node.durationMs)}
                </span>
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
};

export default ExecutionTimeline;
