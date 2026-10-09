import { apiRequest } from "@/config/api";

export type FeedbackStatus = string;

/** A message an admin/supervisor commented on, with its tracked resolution status. */
export interface ReportedFeedbackItem {
  feedback_id: string;
  message_id: string;
  conversation_id: string;
  agent_id: string | null;
  workflow_name: string | null;
  text: string;
  speaker: string;
  comment: string;
  rating: string | null;
  status: FeedbackStatus;
  reported_by: string | null;
  reported_at: string;
  conversation_topic: string | null;
  conversation_subtopic: string | null;
  conversation_date: string | null;
  fix_version: string | null;
  target_rollout_date: string | null;
}

export interface ReportedFeedbackResult {
  items: ReportedFeedbackItem[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface FeedbackFilters {
  /** Filter by when the comment was added (reported time). */
  from_date?: string;
  to_date?: string;
  workflow_id?: string;
  topic?: string;
  subtopic?: string;
}

export interface FetchReportedFeedbackParams extends FeedbackFilters {
  skip?: number;
  limit?: number;
  status?: FeedbackStatus | "all";
}

const MAX_BACKEND_LIMIT = 100;

const appendFilters = (query: URLSearchParams, filters: FeedbackFilters) => {
  for (const key of [
    "from_date",
    "to_date",
    "workflow_id",
    "topic",
    "subtopic",
  ] as const) {
    const value = filters[key];
    if (value) query.append(key, value);
  }
};

const EMPTY_RESULT: ReportedFeedbackResult = {
  items: [],
  total: 0,
  page: 1,
  page_size: 20,
  total_pages: 0,
};

export const fetchReportedFeedback = async (
  params: FetchReportedFeedbackParams = {},
): Promise<ReportedFeedbackResult> => {
  const { skip = 0, limit = 20, status } = params;
  const safeLimit = limit > 0 ? Math.min(limit, MAX_BACKEND_LIMIT) : 20;

  const queryParams = new URLSearchParams();
  if (skip) queryParams.append("skip", String(skip));
  queryParams.append("limit", String(safeLimit));
  if (status && status !== "all") queryParams.append("status", status);
  appendFilters(queryParams, params);

  const response = await apiRequest<ReportedFeedbackResult>(
    "GET",
    `conversations/issues?${queryParams.toString()}`,
  );

  return response ?? EMPTY_RESULT;
};

/** Issue counts per status key, zero-filled over the configured statuses. */
export interface FeedbackStatusSummary {
  total: number;
  by_status: Partial<Record<FeedbackStatus, number>>;
}

export const EMPTY_SUMMARY: FeedbackStatusSummary = { total: 0, by_status: {} };

export const fetchReportedFeedbackSummary = async (
  params: FeedbackFilters = {},
): Promise<FeedbackStatusSummary> => {
  const queryParams = new URLSearchParams();
  appendFilters(queryParams, params);
  const query = queryParams.toString();

  const response = await apiRequest<FeedbackStatusSummary>(
    "GET",
    `conversations/issues/summary${query ? `?${query}` : ""}`,
  );
  return response ?? EMPTY_SUMMARY;
};

/** Partial issue update: an omitted field is kept, an explicit null clears it. */
export type IssuePatch = {
  status?: FeedbackStatus;
  fix_version?: string | null;
  target_rollout_date?: string | null;
};

export interface MessageIssueRow {
  id: string;
  message_feedback_id: string;
  status: FeedbackStatus;
  fix_version: string | null;
  target_rollout_date: string | null;
  resolved_by: string | null;
  resolved_at: string | null;
  updated_at: string | null;
}

export const updateFeedbackIssue = async (
  feedbackId: string,
  patch: IssuePatch,
): Promise<MessageIssueRow> => {
  const row = await apiRequest<MessageIssueRow>(
    "PATCH",
    `conversations/issues/${feedbackId}`,
    patch,
  );
  if (!row) throw new Error("You don't have permission to update this feedback");
  return row;
};

export interface IssueNote {
  id: string;
  message_feedback_id: string;
  author_user_id: string;
  author_username: string | null;
  body: string;
  created_at: string;
}

export const fetchIssueNotes = async (feedbackId: string): Promise<IssueNote[]> => {
  const notes = await apiRequest<IssueNote[]>(
    "GET",
    `conversations/issues/${feedbackId}/notes`,
  );
  return Array.isArray(notes) ? notes : [];
};

export const addIssueNote = async (
  feedbackId: string,
  body: string,
): Promise<IssueNote> => {
  const note = await apiRequest<IssueNote>(
    "POST",
    `conversations/issues/${feedbackId}/notes`,
    { body },
  );
  if (!note) throw new Error("You don't have permission to add a note");
  return note;
};
