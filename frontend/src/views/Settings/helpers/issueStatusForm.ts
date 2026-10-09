import type {
  IssueCategory,
  IssueStatus,
  IssueStatusEdit,
} from "@/services/issueStatuses";
import { activeStatuses } from "@/views/ReportedFeedback/helpers/issueStatuses";

export type IssueStatusFormValues = {
  key: string;
  label: string;
  category: IssueCategory;
  color: string;
};

/** The fixed default status: it cannot be non-active and stays in To Do */
export const DEFAULT_STATUS_KEY = "open";

const KEY_PATTERN = /^[a-z][a-z0-9_]{1,49}$/;

export function issueStatusKeyError(key: string): string | null {
  const value = key.trim();
  if (!value) return "Key is required";
  if (value === "all") return '"all" is reserved';
  if (!KEY_PATTERN.test(value)) {
    return "Use 2-50 lowercase letters, digits or underscores, starting with a letter";
  }
  return null;
}

export function changedFields(
  status: IssueStatus,
  values: IssueStatusFormValues,
): IssueStatusEdit {
  const changes: IssueStatusEdit = {};
  const label = values.label.trim();
  if (label !== status.label) changes.label = label;
  if (values.category !== status.category) changes.category = values.category;
  if (values.color !== status.color) changes.color = values.color;
  return changes;
}

export function moveStatus(
  list: IssueStatus[],
  key: string,
  direction: -1 | 1,
): string[] | null {
  const keys = activeStatuses(list).map((status) => status.key);
  const from = keys.indexOf(key);
  const to = from + direction;
  if (from === -1 || to < 0 || to >= keys.length) return null;
  [keys[from], keys[to]] = [keys[to], keys[from]];
  return keys;
}
