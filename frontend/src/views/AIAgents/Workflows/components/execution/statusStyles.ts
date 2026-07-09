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
    chipClass: 'bg-green-50 text-green-700 border-green-200',
    nodeClass: 'border-green-300 bg-green-50',
    accentClass: 'text-green-600',
  },
  failed: {
    label: 'Failed',
    Icon: XCircle,
    chipClass: 'bg-red-50 text-red-700 border-red-200',
    nodeClass: 'border-red-300 bg-red-50',
    accentClass: 'text-red-600',
  },
  running: {
    label: 'Running',
    Icon: Loader2,
    spin: true,
    chipClass: 'bg-blue-50 text-blue-700 border-blue-200',
    nodeClass: 'border-blue-300 bg-blue-50',
    accentClass: 'text-blue-600',
  },
  skipped: {
    label: 'Skipped',
    Icon: MinusCircle,
    chipClass: 'bg-gray-100 text-gray-600 border-gray-200',
    nodeClass: 'border-gray-300 bg-gray-50',
    accentClass: 'text-gray-500',
  },
  pending: {
    label: 'Not run',
    Icon: Circle,
    chipClass: 'bg-gray-50 text-gray-500 border-gray-200',
    nodeClass: 'border-gray-200 bg-white',
    accentClass: 'text-gray-400',
  },
};

/** Ordered statuses for summary tiles (most relevant first). */
export const SUMMARY_STATUS_ORDER: ExecutionNodeStatus[] = ['completed', 'failed', 'running', 'skipped', 'pending'];
