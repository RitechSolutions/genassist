import type { IssueCategory, IssueStatus } from "@/services/issueStatuses";
import type { FeedbackStatusSummary } from "@/services/reportedFeedback";
import { STATUS_COLOR_CLASSES } from "../constants";

export interface StatusMeta {
  label: string;
  className: string;
}

const FALLBACK_COLOR = STATUS_COLOR_CLASSES.zinc;

export function activeStatuses(list: IssueStatus[]): IssueStatus[] {
  return list.filter((status) => status.is_active === 1);
}

/** Label and classes for a key; unknown keys still render, labelled by the key. */
export function statusMeta(list: IssueStatus[], key: string): StatusMeta {
  const status = list.find((s) => s.key === key);
  if (!status) return { label: key, className: FALLBACK_COLOR };
  return {
    label: status.label,
    className: STATUS_COLOR_CLASSES[status.color] ?? FALLBACK_COLOR,
  };
}

/**
 * Active keys in position order (then retired ones with `includeRetired`), plus
 * `current` when it is not listed, so a select can still show the value it holds.
 */
export function withCurrentStatus(
  list: IssueStatus[],
  current: string | null,
  { includeRetired = false }: { includeRetired?: boolean } = {},
): string[] {
  const retired = includeRetired
    ? list.filter((status) => status.is_active !== 1)
    : [];
  const keys = [...activeStatuses(list), ...retired].map((status) => status.key);
  if (!current || current === "all" || keys.includes(current)) return keys;
  return [...keys, current];
}

export function listableStatuses(
  list: IssueStatus[],
  byStatus: FeedbackStatusSummary["by_status"],
  selected: string[] = [],
): IssueStatus[] {
  const retired = list.filter(
    (status) =>
      status.is_active !== 1 &&
      ((byStatus[status.key] ?? 0) > 0 || selected.includes(status.key)),
  );
  return [...activeStatuses(list), ...retired];
}

export function normalizeStatusKeys(values: string[]): string[] {
  return [...new Set(values.filter(Boolean))].sort();
}

/** Summary counts summed per category; keys the list does not know count nowhere. */
export function categoryTotals(
  summary: FeedbackStatusSummary,
  list: IssueStatus[],
): Record<IssueCategory, number> {
  const totals: Record<IssueCategory, number> = {
    todo: 0,
    in_progress: 0,
    done: 0,
  };
  for (const status of list) {
    if (!(status.category in totals)) continue;
    totals[status.category] += summary.by_status[status.key] ?? 0;
  }
  return totals;
}
