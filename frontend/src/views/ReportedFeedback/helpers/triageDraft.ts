import { format, parseISO } from "date-fns";

import type {
  IssuePatch,
  ReportedFeedbackItem,
} from "@/services/reportedFeedback";

type TriageFields = Pick<
  ReportedFeedbackItem,
  "fix_version" | "target_rollout_date"
>;

export interface TriageDraft {
  fix_version: string;
  target_rollout_date: string | null;
}

export function toDraft(issue: TriageFields): TriageDraft {
  return {
    fix_version: issue.fix_version ?? "",
    target_rollout_date: issue.target_rollout_date,
  };
}

export function draftToPatch(issue: TriageFields, draft: TriageDraft): IssuePatch {
  const patch: IssuePatch = {};
  const fixVersion = draft.fix_version.trim() || null;
  if (fixVersion !== (issue.fix_version ?? null)) patch.fix_version = fixVersion;
  if (draft.target_rollout_date !== (issue.target_rollout_date ?? null)) {
    patch.target_rollout_date = draft.target_rollout_date;
  }
  return patch;
}

export function isDraftDirty(issue: TriageFields, draft: TriageDraft): boolean {
  return Object.keys(draftToPatch(issue, draft)).length > 0;
}

export function formatDateOnly(value: string): string {
  return format(parseISO(value), "d MMM yyyy");
}

export function toDateOnly(date: Date): string {
  return format(date, "yyyy-MM-dd");
}

export function topicLabel(topic: string, subtopic: string | null): string {
  return subtopic ? `${topic} - ${subtopic}` : topic;
}
