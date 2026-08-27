import React, { useMemo } from 'react';
import { ArrowRight } from 'lucide-react';
import { Change, diffWordsWithSpace } from 'diff';
import { isEqual } from 'lodash';
import { cn } from '@/helpers/utils';
import { FieldChange } from '@/interfaces/workflow-diff.interface';

export interface FieldChangeRowProps {
  change: FieldChange;
  className?: string;
}

interface LeafChange {
  path: string;
  before: unknown;
  after: unknown;
}

const SHORT_VALUE_MAX = 60;
// Below this word-level overlap the value was replaced rather than edited (cf. git's -M50%).
const MIN_SIMILARITY = 0.5;
const MAX_DIFF_CHARS = 40000;

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
  if (value === undefined) return 'not set';
  if (value === null) return 'null';
  if (typeof value === 'string') return value === '' ? '""' : value;
  return String(value);
};

/** Which side holds the value when the field/leaf exists on one side only. */
const presentSide = (before: unknown, after: unknown): 'before' | 'after' | null => {
  if (before === undefined && after !== undefined) return 'after';
  if (after === undefined && before !== undefined) return 'before';
  return null;
};

/** Share of the longer side that both versions have in common. */
const overlap = (parts: Change[], beforeLength: number, afterLength: number): number => {
  const longest = Math.max(beforeLength, afterLength);
  if (longest === 0) return 1;
  const common = parts.reduce((sum, part) => (part.added || part.removed ? sum : sum + part.value.length), 0);
  return common / longest;
};

type Rendering =
  | { kind: 'single'; side: 'before' | 'after' }
  | { kind: 'scalar' }
  | { kind: 'replaced' }
  | { kind: 'inline'; parts: Change[] };

const planRendering = (before: unknown, after: unknown): Rendering => {
  const single = presentSide(before, after);
  if (single) return { kind: 'single', side: single };

  const beforeText = formatScalar(before);
  const afterText = formatScalar(after);
  const multiline = beforeText.includes('\n') || afterText.includes('\n');
  const long = beforeText.length > SHORT_VALUE_MAX || afterText.length > SHORT_VALUE_MAX;

  if (!isObj(before) && !isObj(after) && !multiline && !long) return { kind: 'scalar' };

  const diffable =
    typeof before === 'string' &&
    typeof after === 'string' &&
    beforeText.length <= MAX_DIFF_CHARS &&
    afterText.length <= MAX_DIFF_CHARS;
  if (!diffable) return { kind: 'replaced' };

  const parts = diffWordsWithSpace(beforeText, afterText);
  if (overlap(parts, beforeText.length, afterText.length) < MIN_SIMILARITY) return { kind: 'replaced' };
  return { kind: 'inline', parts };
};

const NameBadge: React.FC<{ side: 'before' | 'after' }> = ({ side }) => (
  <span
    className={cn(
      'shrink-0 rounded px-1 py-px text-[9px] font-semibold uppercase tracking-wide',
      side === 'after'
        ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/20 dark:text-emerald-300'
        : 'bg-rose-100 text-rose-700 dark:bg-rose-500/20 dark:text-rose-300'
    )}
  >
    {side === 'after' ? 'new' : 'removed'}
  </span>
);

const InlineTextDiff: React.FC<{ parts: Change[] }> = ({ parts }) => (
  <p className="whitespace-pre-wrap break-words px-2.5 py-2 font-mono text-xs leading-5 text-muted-foreground">
    {parts.map((part, index) => {
      if (part.removed) {
        return (
          <del
            key={index}
            className="rounded-sm bg-rose-100 text-rose-700 no-underline dark:bg-rose-500/25 dark:text-rose-300"
          >
            {part.value}
          </del>
        );
      }
      if (part.added) {
        return (
          <ins
            key={index}
            className="rounded-sm bg-emerald-100 text-emerald-700 no-underline dark:bg-emerald-500/25 dark:text-emerald-300"
          >
            {part.value}
          </ins>
        );
      }
      return <span key={index}>{part.value}</span>;
    })}
  </p>
);

const ScalarRow: React.FC<{ before: unknown; after: unknown }> = ({ before, after }) => {
  const pill = (value: unknown, side: 'before' | 'after') => (
    <span
      className={cn(
        'rounded px-1.5 py-0.5',
        side === 'before'
          ? 'bg-rose-50 text-rose-700 dark:bg-rose-500/15 dark:text-rose-300'
          : 'bg-emerald-50 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300'
      )}
    >
      <span className="sr-only">{side === 'before' ? 'Before: ' : 'After: '}</span>
      {formatScalar(value)}
    </span>
  );

  return (
    <div className="flex flex-wrap items-center gap-2 px-2.5 py-2 font-mono text-xs leading-5">
      {pill(before, 'before')}
      <ArrowRight className="h-3.5 w-3.5 shrink-0 text-muted-foreground" aria-hidden="true" />
      {pill(after, 'after')}
    </div>
  );
};

const ValueLine: React.FC<{ side: 'before' | 'after'; value: unknown; glyph?: boolean }> = ({
  side,
  value,
  glyph = true,
}) => {
  const removed = side === 'before';

  return (
    <div
      className={cn(
        'flex items-start gap-2 px-2.5 py-1.5',
        removed ? 'bg-rose-50/50 dark:bg-rose-500/15' : 'bg-emerald-50/50 dark:bg-emerald-500/15'
      )}
    >
      {glyph && (
        <span
          className={cn(
            'mt-px select-none font-mono text-xs font-semibold leading-5',
            removed ? 'text-rose-500' : 'text-emerald-600 dark:text-emerald-400'
          )}
          aria-hidden="true"
        >
          {removed ? '−' : '+'}
        </span>
      )}
      <span className="sr-only">{removed ? 'Before:' : 'After:'}</span>
      {isObj(value) ? (
        <pre className="min-w-0 flex-1 whitespace-pre-wrap break-words font-mono text-[11px] leading-5 text-muted-foreground">
          {JSON.stringify(value, null, 2)}
        </pre>
      ) : (
        <span
          className={cn(
            'min-w-0 flex-1 whitespace-pre-wrap break-words font-mono text-xs leading-5',
            removed ? 'text-rose-700 dark:text-rose-400' : 'text-emerald-700 dark:text-emerald-400'
          )}
        >
          {formatScalar(value)}
        </span>
      )}
    </div>
  );
};

const ChangeBody: React.FC<{ before: unknown; after: unknown }> = ({ before, after }) => {
  const plan = useMemo(() => planRendering(before, after), [before, after]);

  if (plan.kind === 'single') {
    return <ValueLine side={plan.side} value={plan.side === 'after' ? after : before} glyph={false} />;
  }
  if (plan.kind === 'scalar') return <ScalarRow before={before} after={after} />;
  if (plan.kind === 'inline') return <InlineTextDiff parts={plan.parts} />;
  return (
    <div className="divide-y divide-border">
      <ValueLine side="before" value={before} />
      <ValueLine side="after" value={after} />
    </div>
  );
};

const FieldChangeRow: React.FC<FieldChangeRowProps> = ({ change, className }) => {
  // For object/array values, surface only the nested leaves that changed rather than the whole blob.
  const leaves = useMemo(() => {
    if (!isObj(change.before) || !isObj(change.after)) return null;
    const out: LeafChange[] = [];
    collectLeafChanges(change.before, change.after, '', out);
    return out;
  }, [change.before, change.after]);

  const fieldSide = presentSide(change.before, change.after);

  return (
    <div className={cn('overflow-hidden rounded-md border border-border bg-card', className)}>
      <div className="flex items-center justify-between gap-2 border-b border-border bg-muted/80 px-2.5 py-1">
        <span className="flex min-w-0 items-center gap-1.5">
          <span className="truncate font-mono text-[11px] font-medium text-muted-foreground">{change.key}</span>
          {fieldSide && <NameBadge side={fieldSide} />}
        </span>
        {leaves && leaves.length > 0 && (
          <span className="shrink-0 text-[10px] tabular-nums text-muted-foreground">
            {leaves.length} {leaves.length === 1 ? 'change' : 'changes'}
          </span>
        )}
      </div>

      {leaves ? (
        leaves.length > 0 ? (
          <div className="divide-y divide-border">
            {leaves.map((leaf) => {
              const leafSide = presentSide(leaf.before, leaf.after);
              return (
                <div key={leaf.path}>
                  <div className="flex items-center gap-1.5 bg-card px-2.5 py-2">
                    <span className="truncate font-mono text-[10px] text-muted-foreground">{leaf.path}</span>
                    {leafSide && <NameBadge side={leafSide} />}
                  </div>
                  <ChangeBody before={leaf.before} after={leaf.after} />
                </div>
              );
            })}
          </div>
        ) : (
          <div className="px-2.5 py-2 text-[11px] italic text-muted-foreground">Reordered — same values.</div>
        )
      ) : (
        <ChangeBody before={change.before} after={change.after} />
      )}
    </div>
  );
};

export default FieldChangeRow;
