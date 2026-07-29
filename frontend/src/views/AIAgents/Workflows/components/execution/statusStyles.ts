import { CheckCircle2, XCircle, Loader2, MinusCircle, Circle, LucideIcon } from 'lucide-react';
import { ExecutionNodeStatus } from '@/interfaces/workflow-execution.interface';

/**
 * Visual treatment per node status. Status is conveyed by icon + text label as well as color
 * (never color alone) to meet the accessibility bar (spec NFR / a11y).
 */
export interface StatusStyle {
  label: string;
  Icon: LucideIcon;
  /** Whether the icon should spin (running). */
  spin?: boolean;
  /** Badge/chip classes (bg + text + border). */
  chipClass: string;
  /** Node card border + subtle background. */
  nodeClass: string;
  /** Small dot / accent color class (text-*). */
  accentClass: string;
}

export const STATUS_STYLES: Record<ExecutionNodeStatus, StatusStyle> = {
  completed: {
    label: 'Completed',
    Icon: CheckCircle2,
    chipClass: 'bg-green-50 text-green-700 border-green-200 dark:bg-green-500/15 dark:text-green-400 dark:border-green-500/30',
    nodeClass: 'border-green-300 bg-green-50 dark:border-green-500/40 dark:bg-green-500/10',
    accentClass: 'text-green-600 dark:text-green-400',
  },
  failed: {
    label: 'Failed',
    Icon: XCircle,
    chipClass: 'bg-red-50 text-red-700 border-red-200 dark:bg-red-500/15 dark:text-red-400 dark:border-red-500/30',
    nodeClass: 'border-red-300 bg-red-50 dark:border-red-500/40 dark:bg-red-500/10',
    accentClass: 'text-red-600 dark:text-red-400',
  },
  running: {
    label: 'Running',
    Icon: Loader2,
    spin: true,
    chipClass: 'bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-500/15 dark:text-blue-400 dark:border-blue-500/30',
    nodeClass: 'border-blue-300 bg-blue-50 dark:border-blue-500/40 dark:bg-blue-500/10',
    accentClass: 'text-blue-600 dark:text-blue-400',
  },
  skipped: {
    label: 'Skipped',
    Icon: MinusCircle,
    chipClass: 'bg-gray-100 text-gray-600 border-gray-200 dark:bg-zinc-700/40 dark:text-zinc-400 dark:border-zinc-600/50',
    nodeClass: 'border-gray-300 bg-gray-50 dark:border-zinc-600/60 dark:bg-zinc-800/60',
    accentClass: 'text-gray-500 dark:text-zinc-400',
  },
  pending: {
    label: 'Not run',
    Icon: Circle,
    chipClass: 'bg-gray-50 text-gray-500 border-gray-200 dark:bg-zinc-800/60 dark:text-zinc-500 dark:border-zinc-700',
    nodeClass: 'border-gray-200 bg-white dark:border-zinc-700 dark:bg-zinc-800/40',
    accentClass: 'text-gray-400 dark:text-zinc-500',
  },
};

/** Ordered statuses for summary tiles (most relevant first). */
export const SUMMARY_STATUS_ORDER: ExecutionNodeStatus[] = ['completed', 'failed', 'running', 'skipped', 'pending'];
