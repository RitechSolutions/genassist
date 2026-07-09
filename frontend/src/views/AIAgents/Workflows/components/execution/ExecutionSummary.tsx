import React from 'react';
import { cn } from '@/helpers/utils';
import { ExecutionViewModel } from '@/interfaces/workflow-execution.interface';
import { formatDuration } from '../../utils/executionView';
import { STATUS_STYLES, SUMMARY_STATUS_ORDER } from './statusStyles';

/**
 * Run-level summary shown above the execution graph as a single thin strip so the graph and
 * detail panel get the vertical space: node count, total steps, overall duration, slowest node,
 * and per-status counts. See spec FR-4 / FR-6 / AC-2 / AC-3.
 */
interface ExecutionSummaryProps {
  model: ExecutionViewModel;
}

const Metric: React.FC<{ label: string; value: React.ReactNode; title?: string }> = ({ label, value, title }) => (
  <span className="flex items-center gap-1 whitespace-nowrap" title={title}>
    <span className="text-gray-400">{label}</span>
    <span className="max-w-[140px] truncate font-semibold tabular-nums text-gray-800">{value}</span>
  </span>
);

const ExecutionSummary: React.FC<ExecutionSummaryProps> = ({ model }) => {
  const slowest = model.slowestNodeId ? model.byId[model.slowestNodeId] : undefined;

  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 rounded-md border border-gray-200 bg-gray-50/70 px-3 py-1.5 text-xs">
      <Metric label="Nodes" value={model.totalNodes} />
      <Metric label="Steps" value={model.totalSteps ?? '—'} />
      <Metric label="Duration" value={formatDuration(model.overallDurationMs)} />
      {slowest && (
        <Metric
          label="Slowest"
          value={slowest.name}
          title={`${slowest.name} · ${formatDuration(slowest.durationMs)}`}
        />
      )}

      <span className="mx-0.5 h-4 w-px bg-gray-200" aria-hidden="true" />

      <span className="flex flex-wrap items-center gap-1.5" role="list" aria-label="Node status counts">
        {SUMMARY_STATUS_ORDER.filter((status) => model.counts[status] > 0).map((status) => {
          const style = STATUS_STYLES[status];
          const { Icon } = style;
          return (
            <span
              key={status}
              role="listitem"
              className={cn(
                'inline-flex items-center gap-1 rounded-full border px-1.5 py-0.5 font-medium',
                style.chipClass
              )}
              title={`${style.label}: ${model.counts[status]}`}
            >
              <Icon className={cn('h-3 w-3', style.spin && 'animate-spin')} aria-hidden="true" />
              <span className="sr-only">{style.label}: </span>
              {model.counts[status]}
            </span>
          );
        })}
      </span>
    </div>
  );
};

export default ExecutionSummary;
