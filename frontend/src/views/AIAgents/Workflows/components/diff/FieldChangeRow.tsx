import React, { useMemo } from 'react';
import { isEqual } from 'lodash';
import { cn } from '@/helpers/utils';
import { FieldChange } from '@/interfaces/workflow-diff.interface';

/**
 * One field-level change (old→new) for a modified node, rendered as a GitHub-style stacked diff
 * (spec FR-6, AC-9): a removed (−) line over an added (+) line. Scalars sit inline in a mono font.
 * For objects/arrays we don't dump the whole value twice — we recurse and surface only the nested
 * leaf paths that actually differ (e.g. `message.description`), so the reader sees exactly what
 * changed inside a large config. A missing side (field/leaf added or removed) is shown explicitly.
 */
export interface FieldChangeRowProps {
  change: FieldChange;
  className?: string;
}

interface LeafChange {
  path: string;
  before: unknown;
  after: unknown;
}

const isObj = (value: unknown): boolean => value !== null && typeof value === 'object';

/** Walk two values in parallel, collecting only the leaf paths whose values differ. */
const collectLeafChanges = (before: unknown, after: unknown, path: string, out: LeafChange[]): void => {
  if (isEqual(before, after)) return;
  if (isObj(before) && isObj(after)) {
    const b = before as Record<string, unknown>;
    const a = after as Record<string, unknown>;
    const keys = Array.from(new Set([...Object.keys(b), ...Object.keys(a)]));
    for (const key of keys) {
      collectLeafChanges(b[key], a[key], path ? `${path}.${key}` : key, out);
    }
    return;
  }
  out.push({ path, before, after });
};

const formatScalar = (value: unknown): string => {
  if (value === undefined) return '—';
  if (value === null) return 'null';
  if (typeof value === 'string') return value === '' ? '""' : value;
  return String(value);
};

const ValueLine: React.FC<{ side: 'before' | 'after'; value: unknown }> = ({ side, value }) => {
  const removed = side === 'before';
  const absent = value === undefined;
  const complex = isObj(value);

  return (
    <div className={cn('flex items-start gap-2 px-2.5 py-1.5', removed ? 'bg-rose-50/50' : 'bg-emerald-50/50')}>
      <span
        className={cn(
          'mt-px select-none font-mono text-xs font-semibold leading-5',
          removed ? 'text-rose-500' : 'text-emerald-600'
        )}
        aria-hidden="true"
      >
        {removed ? '−' : '+'}
      </span>
      <span className="sr-only">{removed ? 'Before:' : 'After:'}</span>
      {complex ? (
        <pre className="min-w-0 flex-1 overflow-x-auto whitespace-pre font-mono text-[11px] leading-5 text-slate-600">
          {JSON.stringify(value, null, 2)}
        </pre>
      ) : (
        <span
          className={cn(
            'min-w-0 flex-1 whitespace-pre-wrap break-words font-mono text-xs leading-5',
            absent ? 'italic text-slate-400' : removed ? 'text-rose-700' : 'text-emerald-700'
          )}
        >
          {formatScalar(value)}
        </span>
      )}
    </div>
  );
};

const StackedDiff: React.FC<{ before: unknown; after: unknown }> = ({ before, after }) => (
  <div className="divide-y divide-slate-100">
    <ValueLine side="before" value={before} />
    <ValueLine side="after" value={after} />
  </div>
);

const FieldChangeRow: React.FC<FieldChangeRowProps> = ({ change, className }) => {
  // For object/array values, surface only the nested leaves that changed rather than the whole blob.
  const leaves = useMemo(() => {
    if (!isObj(change.before) || !isObj(change.after)) return null;
    const out: LeafChange[] = [];
    collectLeafChanges(change.before, change.after, '', out);
    return out;
  }, [change.before, change.after]);

  return (
    <div className={cn('overflow-hidden rounded-md border border-slate-200 bg-white', className)}>
      <div className="flex items-center justify-between border-b border-slate-100 bg-slate-50/80 px-2.5 py-1">
        <span className="font-mono text-[11px] font-medium text-slate-600">{change.key}</span>
        {leaves && leaves.length > 0 && (
          <span className="text-[10px] tabular-nums text-slate-400">
            {leaves.length} {leaves.length === 1 ? 'change' : 'changes'}
          </span>
        )}
      </div>

      {leaves ? (
        leaves.length > 0 ? (
          <div className="divide-y divide-slate-100">
            {leaves.map((leaf) => (
              <div key={leaf.path}>
                <div className="bg-white px-2.5 pt-1.5 font-mono text-[10px] text-slate-400">{leaf.path}</div>
                <StackedDiff before={leaf.before} after={leaf.after} />
              </div>
            ))}
          </div>
        ) : (
          <div className="px-2.5 py-2 text-[11px] italic text-slate-400">Reordered — same values.</div>
        )
      ) : (
        <StackedDiff before={change.before} after={change.after} />
      )}
    </div>
  );
};

export default FieldChangeRow;
