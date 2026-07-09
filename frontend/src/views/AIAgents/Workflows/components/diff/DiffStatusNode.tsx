import React from 'react';
import { NodeProps } from 'reactflow';
import { cn } from '@/helpers/utils';
import { NodeDiffStatus } from '@/interfaces/workflow-diff.interface';
import { NodeData, NodeHandler } from '../../types/nodes';
import { HandlersRenderer } from '../custom/HandleTooltip';
import { DIFF_STATUS_STYLES } from './diffStatusStyles';

/**
 * Read-only reactflow node used by the side-by-side diff graph. It renders the node name and a
 * diff-status badge (icon + text label + color, never color alone — spec FR-14). Edge handles are
 * rendered from `data.handlers` via the shared `HandlersRenderer` so multi-handle/router edges
 * still resolve their `sourceHandle`/`targetHandle`. Mirrors `ExecutionStatusNode`.
 */
export interface DiffStatusNodeData {
  name: string;
  handlers?: NodeHandler[];
  status: NodeDiffStatus;
  fieldChangeCount: number;
  isSelected?: boolean;
}

const DiffStatusNodeComponent: React.FC<NodeProps<DiffStatusNodeData>> = ({ id, data }) => {
  const style = DIFF_STATUS_STYLES[data.status] ?? DIFF_STATUS_STYLES.unchanged;
  const { Icon } = style;

  return (
    <div
      className={cn(
        'relative w-[210px] rounded-lg border border-slate-200 border-l-[3px] bg-white px-3 py-2 shadow-sm transition-shadow',
        style.railClass,
        data.isSelected ? 'shadow-md ring-2 ring-brand-600 ring-offset-2' : 'hover:shadow-md'
      )}
    >
      {/* Edge handles driven by the node's own handler config (reused renderer). */}
      <HandlersRenderer id={id} data={data as unknown as NodeData} />

      <div className="flex items-center gap-1.5">
        <span className={cn('h-2 w-2 shrink-0 rounded-full', style.dotClass)} aria-hidden="true" />
        <span className="truncate text-sm font-medium text-slate-700" title={data.name}>
          {data.name}
        </span>
      </div>

      <div className="mt-1.5 flex items-center justify-between gap-2">
        <span
          className={cn(
            'inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-[10px] font-medium',
            style.chipClass
          )}
        >
          <Icon className="h-3 w-3" aria-hidden="true" />
          {style.label}
        </span>
        {data.status === 'modified' && data.fieldChangeCount > 0 && (
          <span className="text-[10px] tabular-nums text-slate-400">
            {data.fieldChangeCount} {data.fieldChangeCount === 1 ? 'field' : 'fields'}
          </span>
        )}
      </div>
    </div>
  );
};

export const DiffStatusNode = React.memo(DiffStatusNodeComponent);
export default DiffStatusNode;
