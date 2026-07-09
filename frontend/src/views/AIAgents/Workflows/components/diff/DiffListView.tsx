import React, { useMemo } from 'react';
import { Check, ArrowRight } from 'lucide-react';
import { cn } from '@/helpers/utils';
import { ScrollArea } from '@/components/scroll-area';
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '@/components/accordion';
import { NodeDiff, NodeDiffStatus, WorkflowDiff } from '@/interfaces/workflow-diff.interface';
import { DIFF_STATUS_ORDER, DIFF_STATUS_STYLES } from './diffStatusStyles';
import FieldChangeRow from './FieldChangeRow';

/**
 * Grouped-list presentation of a workflow diff (spec FR-4/FR-5/FR-6/FR-8, the default view). A
 * segmented summary strip leads, followed by collapsible sections for Modified (expanding to
 * field-level old→new rows), Added and Removed nodes, plus Added/Removed connections. Renders a
 * clear "no differences" state when the two versions are identical (FR-9, AC-6).
 */
export interface DiffListViewProps {
  diff: WorkflowDiff;
}

/** A node identity row with a left accent rail (added/removed sections). */
const NodeIdentityRow: React.FC<{ node: NodeDiff }> = ({ node }) => {
  const style = DIFF_STATUS_STYLES[node.status];
  return (
    <div
      className={cn(
        'flex items-center gap-2.5 rounded-md border border-slate-200 border-l-[3px] bg-white px-3 py-2',
        style.railClass
      )}
    >
      <span className={cn('h-1.5 w-1.5 shrink-0 rounded-full', style.dotClass)} aria-hidden="true" />
      <span className="sr-only">{style.label}:</span>
      <span className="flex-1 truncate text-sm font-medium text-slate-700" title={node.label}>
        {node.label}
      </span>
      <span className="shrink-0 rounded border border-slate-200 bg-slate-50 px-1.5 py-0.5 font-mono text-[10px] text-slate-500">
        {node.type}
      </span>
    </div>
  );
};

/** Section header: uppercase label + count in a compact square. */
const SectionLabel: React.FC<{ children: React.ReactNode; count: number }> = ({ children, count }) => (
  <span className="flex items-center gap-2">
    <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">{children}</span>
    <span className="inline-flex h-5 min-w-[1.25rem] items-center justify-center rounded-md bg-slate-100 px-1 text-[11px] font-semibold tabular-nums text-slate-500">
      {count}
    </span>
  </span>
);

const DiffListView: React.FC<DiffListViewProps> = ({ diff }) => {
  const { summary, nodes, edges } = diff;

  const modified = useMemo(() => nodes.filter((n) => n.status === 'modified'), [nodes]);
  const added = useMemo(() => nodes.filter((n) => n.status === 'added'), [nodes]);
  const removed = useMemo(() => nodes.filter((n) => n.status === 'removed'), [nodes]);
  const addedEdges = useMemo(() => edges.filter((e) => e.status === 'added'), [edges]);
  const removedEdges = useMemo(() => edges.filter((e) => e.status === 'removed'), [edges]);

  const hasNodeChanges = summary.added + summary.removed + summary.modified > 0;
  const hasChanges = hasNodeChanges || edges.length > 0;

  const defaultOpen = useMemo(() => {
    const open: string[] = [];
    if (modified.length) open.push('modified');
    if (added.length) open.push('added');
    if (removed.length) open.push('removed');
    if (edges.length) open.push('connections');
    return open;
  }, [modified.length, added.length, removed.length, edges.length]);

  return (
    <div className="flex h-full flex-col">
      {/* Summary strip (FR-4): one calm segmented row of stat tiles. */}
      <div
        className="grid grid-cols-4 divide-x divide-slate-100 overflow-hidden rounded-lg border border-slate-200 bg-white"
        role="list"
        aria-label="Change summary"
      >
        {DIFF_STATUS_ORDER.map((status: NodeDiffStatus) => {
          const style = DIFF_STATUS_STYLES[status];
          const value = summary[status];
          const active = value > 0 && status !== 'unchanged';
          return (
            <div key={status} role="listitem" className="flex items-center gap-2.5 px-3 py-2.5">
              <span
                className={cn('h-2 w-2 shrink-0 rounded-full', active ? style.dotClass : 'bg-slate-200')}
                aria-hidden="true"
              />
              <div className="flex min-w-0 flex-col leading-tight">
                <span
                  className={cn('text-lg font-semibold tabular-nums', active ? 'text-slate-800' : 'text-slate-400')}
                >
                  {value}
                </span>
                <span className="truncate text-[11px] font-medium uppercase tracking-wide text-slate-400">
                  {style.label}
                </span>
              </div>
            </div>
          );
        })}
      </div>

      {!hasChanges ? (
        <div className="flex flex-1 flex-col items-center justify-center gap-3 py-12 text-center">
          <span className="flex h-11 w-11 items-center justify-center rounded-full bg-emerald-50 ring-1 ring-emerald-100">
            <Check className="h-5 w-5 text-emerald-600" aria-hidden="true" />
          </span>
          <p className="text-sm font-medium text-slate-700">No differences</p>
          <p className="max-w-xs text-xs text-slate-500">
            These two versions are identical — no nodes or connections were added, removed, or modified.
          </p>
        </div>
      ) : (
        <ScrollArea className="mt-4 flex-1 pr-3">
          <Accordion type="multiple" defaultValue={defaultOpen} className="w-full space-y-3">
            {modified.length > 0 && (
              <AccordionItem value="modified" className="border-none">
                <AccordionTrigger className="py-1 hover:no-underline">
                  <SectionLabel count={modified.length}>Modified nodes</SectionLabel>
                </AccordionTrigger>
                <AccordionContent className="space-y-2 pt-1">
                  <Accordion type="multiple" className="w-full space-y-2">
                    {modified.map((node) => {
                      const style = DIFF_STATUS_STYLES.modified;
                      return (
                        <AccordionItem
                          key={node.id}
                          value={node.id}
                          className={cn(
                            'overflow-hidden rounded-md border border-slate-200 border-l-[3px] bg-white',
                            style.railClass
                          )}
                        >
                          <AccordionTrigger className="px-3 py-2 hover:no-underline">
                            <span className="flex min-w-0 flex-1 items-center gap-2.5">
                              <span
                                className={cn('h-1.5 w-1.5 shrink-0 rounded-full', style.dotClass)}
                                aria-hidden="true"
                              />
                              <span className="truncate text-sm font-medium text-slate-700">{node.label}</span>
                              <span className="shrink-0 rounded border border-slate-200 bg-slate-50 px-1.5 py-0.5 font-mono text-[10px] text-slate-500">
                                {node.type}
                              </span>
                              <span className="ml-auto shrink-0 pr-2 text-[11px] tabular-nums text-slate-400">
                                {node.fieldChanges.length} {node.fieldChanges.length === 1 ? 'field' : 'fields'}
                              </span>
                            </span>
                          </AccordionTrigger>
                          <AccordionContent className="space-y-2 border-t border-slate-100 bg-slate-50/40 px-3 py-2.5">
                            {node.fieldChanges.map((change) => (
                              <FieldChangeRow key={change.key} change={change} />
                            ))}
                          </AccordionContent>
                        </AccordionItem>
                      );
                    })}
                  </Accordion>
                </AccordionContent>
              </AccordionItem>
            )}

            {added.length > 0 && (
              <AccordionItem value="added" className="border-none">
                <AccordionTrigger className="py-1 hover:no-underline">
                  <SectionLabel count={added.length}>Added nodes</SectionLabel>
                </AccordionTrigger>
                <AccordionContent className="space-y-2 pt-1">
                  {added.map((node) => (
                    <NodeIdentityRow key={node.id} node={node} />
                  ))}
                </AccordionContent>
              </AccordionItem>
            )}

            {removed.length > 0 && (
              <AccordionItem value="removed" className="border-none">
                <AccordionTrigger className="py-1 hover:no-underline">
                  <SectionLabel count={removed.length}>Removed nodes</SectionLabel>
                </AccordionTrigger>
                <AccordionContent className="space-y-2 pt-1">
                  {removed.map((node) => (
                    <NodeIdentityRow key={node.id} node={node} />
                  ))}
                </AccordionContent>
              </AccordionItem>
            )}

            {edges.length > 0 && (
              <AccordionItem value="connections" className="border-none">
                <AccordionTrigger className="py-1 hover:no-underline">
                  <span className="flex items-center gap-2">
                    <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">Connections</span>
                    <span className="flex items-center gap-1.5 text-[11px] font-medium tabular-nums">
                      <span className="text-emerald-600">+{addedEdges.length}</span>
                      <span className="text-slate-300">/</span>
                      <span className="text-rose-600">−{removedEdges.length}</span>
                    </span>
                  </span>
                </AccordionTrigger>
                <AccordionContent className="space-y-2 pt-1">
                  {edges.map((edge) => {
                    const style = edge.status === 'added' ? DIFF_STATUS_STYLES.added : DIFF_STATUS_STYLES.removed;
                    return (
                      <div
                        key={`${edge.status}-${edge.id}`}
                        className={cn(
                          'flex items-center gap-2.5 rounded-md border border-slate-200 border-l-[3px] bg-white px-3 py-2 text-sm',
                          style.railClass
                        )}
                      >
                        <span
                          className={cn('shrink-0 select-none font-mono text-sm font-semibold', style.accentClass)}
                          aria-hidden="true"
                        >
                          {style.glyph}
                        </span>
                        <span className="sr-only">{style.label} connection:</span>
                        <span className="truncate font-medium text-slate-700">{edge.sourceLabel}</span>
                        <ArrowRight className="h-3.5 w-3.5 shrink-0 text-slate-300" aria-hidden="true" />
                        <span className="truncate font-medium text-slate-700">{edge.targetLabel}</span>
                      </div>
                    );
                  })}
                </AccordionContent>
              </AccordionItem>
            )}
          </Accordion>
        </ScrollArea>
      )}
    </div>
  );
};

export default DiffListView;
