import React from 'react';
import { X } from 'lucide-react';
import { cn } from '@/helpers/utils';
import JsonViewer from '@/components/JsonViewer';
import { NodeExecutionView } from '@/interfaces/workflow-execution.interface';
import { formatDuration } from '../../utils/executionView';
import { STATUS_STYLES } from './statusStyles';

/**
 * Details of the node the user selected in the graph: status, timing, input, output and error.
 * See spec FR-7 / AC-4.
 */
interface NodeDetailPanelProps {
  node: NodeExecutionView | null;
  onClose: () => void;
}

const toJsonValue = (value: unknown): React.ComponentProps<typeof JsonViewer>['data'] =>
  // JsonViewer accepts any JSON-serializable value; narrow here to satisfy its prop type.
  value as React.ComponentProps<typeof JsonViewer>['data'];

/**
 * "Marker applied" is our decision to cache, not the outcome. The provider may
 * still reject it (e.g., short prompt below minimum). The actual result comes from
 * what the run reported.
 */
const promptCachingLine = (diagnostic: NonNullable<NodeExecutionView['promptCaching']>): string => {
  if (!diagnostic.applied) {
    return 'Prompt caching: requested but not applied';
  }
  const { cacheReadTokens, cacheCreationTokens } = diagnostic;
  if (cacheReadTokens === undefined && cacheCreationTokens === undefined) {
    return 'Prompt caching: cache marker applied';
  }
  if (!cacheReadTokens && !cacheCreationTokens) {
    return 'Prompt caching: cache marker applied — the provider reported no cache activity';
  }
  const read = (cacheReadTokens ?? 0).toLocaleString();
  const written = (cacheCreationTokens ?? 0).toLocaleString();
  return `Prompt caching: cache marker applied — ${read} tokens read from cache, ${written} written`;
};

const NodeDetailPanel: React.FC<NodeDetailPanelProps> = ({ node, onClose }) => {
  if (!node) {
    return (
      <div className="flex h-full items-center justify-center p-6 text-center text-sm text-muted-foreground">
        Select a node in the graph to inspect its input, output and status.
      </div>
    );
  }

  const style = STATUS_STYLES[node.status] ?? STATUS_STYLES.pending;
  const { Icon } = style;

  return (
    <div className="flex h-full flex-col bg-card">
      <div className="flex items-center justify-between gap-2 border-b border-border px-4 py-3">
        <div className="min-w-0">
          <div className="truncate text-base font-semibold text-foreground" title={node.name}>
            {node.name}
          </div>
          <div className="mt-0.5 flex flex-wrap items-center gap-2">
            {node.type && <div className="text-xs text-muted-foreground">{node.type}</div>}
            <span
              className={cn(
                'inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium',
                style.chipClass
              )}
            >
              <Icon className={cn('h-3 w-3', style.spin && 'animate-spin')} aria-hidden="true" />
              {style.label}
            </span>
            <span className="text-xs text-muted-foreground">
              Duration: <span className="tabular-nums">{formatDuration(node.durationMs)}</span>
            </span>
          </div>
          {node.promptCaching && (
            <div className="mt-1 text-xs text-muted-foreground">{promptCachingLine(node.promptCaching)}</div>
          )}
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close node details"
          className="rounded-md p-1.5 text-muted-foreground hover:bg-muted hover:text-muted-foreground"
        >
          <X className="h-5 w-5" />
        </button>
      </div>

      <div className="flex-1 space-y-4 overflow-y-auto p-4">
        {node.error && (
          <div className="rounded-md border border-red-200 bg-red-50 p-2 text-xs text-red-700 dark:border-red-500/30 dark:bg-red-500/15 dark:text-red-400">
            <div className="mb-1 font-semibold uppercase tracking-wide">Error</div>
            <div className="whitespace-pre-wrap break-words">{node.error}</div>
          </div>
        )}

        <div>
          {node.input === undefined || node.input === null ? (
            <>
              <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Input</div>
              <div className="text-xs text-muted-foreground">No input recorded</div>
            </>
          ) : (
            <JsonViewer
              name="Input"
              data={toJsonValue(node.input)}
              onCopy={(data) => navigator.clipboard.writeText(JSON.stringify(data, null, 2))}
            />
          )}
        </div>

        <div>
          {node.output === undefined || node.output === null ? (
            <>
              <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Output</div>
              <div className="text-xs text-muted-foreground">No output recorded</div>
            </>
          ) : (
            <JsonViewer
              name="Output"
              data={toJsonValue(node.output)}
              onCopy={(data) => navigator.clipboard.writeText(JSON.stringify(data, null, 2))}
            />
          )}
        </div>
      </div>
    </div>
  );
};

export default NodeDetailPanel;
