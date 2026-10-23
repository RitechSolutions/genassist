import type {
  IssuePatch,
  MessageIssueRow,
  ReportedFeedbackItem,
} from "@/services/reportedFeedback";

export type IssueFields = Partial<ReportedFeedbackItem>;

/** Returns a new list with `fields` merged into one row; other rows keep their identity. */
export function applyIssuePatch(
  rows: ReportedFeedbackItem[],
  feedbackId: string,
  fields: IssueFields,
): ReportedFeedbackItem[] {
  return rows.map((row) =>
    row.feedback_id === feedbackId ? { ...row, ...fields } : row,
  );
}

/** The source's values of exactly the keys a patch changes. */
export function pickPatchedFields(
  source: ReportedFeedbackItem | MessageIssueRow,
  patch: IssuePatch,
): IssueFields {
  const fields: IssueFields = {};
  if ("status" in patch) fields.status = source.status;
  if ("fix_version" in patch) fields.fix_version = source.fix_version;
  if ("target_rollout_date" in patch) {
    fields.target_rollout_date = source.target_rollout_date;
  }
  return fields;
}
