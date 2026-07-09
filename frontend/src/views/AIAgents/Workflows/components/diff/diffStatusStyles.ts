import { Plus, Minus, PenLine, Equal, LucideIcon } from 'lucide-react';
import { NodeDiffStatus } from '@/interfaces/workflow-diff.interface';

/**
 * Visual language for the version diff. Deliberately restrained: colour is carried by a thin left
 * accent rail + a small solid dot/icon rather than flooding whole cards with a tint, so the view
 * reads calm and "engineered" rather than candy-coloured. Status is always backed by an icon + a
 * text label + a glyph (never colour alone) to meet the a11y bar (spec FR-14 / NFR a11y).
 *
 * Palette: emerald (added) · rose (removed) · amber (modified) · slate (unchanged). Interactive
 * accents (tabs, selection) use the app brand indigo elsewhere.
 */
export interface DiffStatusStyle {
  label: string;
  /** Compact glyph for dense contexts (+, −, ~, =). */
  glyph: string;
  Icon: LucideIcon;
  /** Icon / accent text colour. */
  accentClass: string;
  /** Solid dot colour (summary tiles, node cards). */
  dotClass: string;
  /** Left accent rail colour (border-l). */
  railClass: string;
  /** Very subtle row/card wash — used sparingly. */
  softClass: string;
  /** Small outlined chip (graph node badge, detail header). */
  chipClass: string;
}

export const DIFF_STATUS_STYLES: Record<NodeDiffStatus, DiffStatusStyle> = {
  added: {
    label: 'Added',
    glyph: '+',
    Icon: Plus,
    accentClass: 'text-emerald-600',
    dotClass: 'bg-emerald-500',
    railClass: 'border-l-emerald-400',
    softClass: 'bg-emerald-50/50',
    chipClass: 'border-emerald-200 bg-emerald-50 text-emerald-700',
  },
  removed: {
    label: 'Removed',
    glyph: '−',
    Icon: Minus,
    accentClass: 'text-rose-600',
    dotClass: 'bg-rose-500',
    railClass: 'border-l-rose-400',
    softClass: 'bg-rose-50/50',
    chipClass: 'border-rose-200 bg-rose-50 text-rose-700',
  },
  modified: {
    label: 'Modified',
    glyph: '~',
    Icon: PenLine,
    // GenAssist brand indigo (only brand-50 / brand-600 are defined; softer shades via opacity).
    accentClass: 'text-brand-600',
    dotClass: 'bg-brand-600',
    railClass: 'border-l-brand-600',
    softClass: 'bg-brand-50',
    chipClass: 'border-brand-600/20 bg-brand-50 text-brand-600',
  },
  unchanged: {
    label: 'Unchanged',
    glyph: '=',
    Icon: Equal,
    accentClass: 'text-slate-400',
    dotClass: 'bg-slate-300',
    railClass: 'border-l-slate-200',
    softClass: 'bg-transparent',
    chipClass: 'border-slate-200 bg-slate-50 text-slate-500',
  },
};

/** Ordered statuses for summary tiles / grouped sections (most relevant first). */
export const DIFF_STATUS_ORDER: NodeDiffStatus[] = ['added', 'removed', 'modified', 'unchanged'];
