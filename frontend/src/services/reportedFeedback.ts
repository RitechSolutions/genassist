import { apiRequest } from "@/config/api";

export type FeedbackStatus = "open" | "in_progress" | "resolved" | "wont_fix";

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
  conversation_date: string | null;
}

export interface ReportedFeedbackResult {
  items: ReportedFeedbackItem[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface FetchReportedFeedbackParams {
  skip?: number;
  limit?: number;
  status?: FeedbackStatus | "all";
  /** Filter by when the comment was added (reported time). */
  from_date?: string;
  to_date?: string;
  workflow_id?: string;
}

const MAX_BACKEND_LIMIT = 100;

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
  const { skip = 0, limit = 20, status, from_date, to_date, workflow_id } = params;
  const safeLimit = limit > 0 ? Math.min(limit, MAX_BACKEND_LIMIT) : 20;

  const queryParams = new URLSearchParams();
  if (skip) queryParams.append("skip", String(skip));
  queryParams.append("limit", String(safeLimit));
  if (status && status !== "all") queryParams.append("status", status);
  if (from_date) queryParams.append("from_date", from_date);
  if (to_date) queryParams.append("to_date", to_date);
  if (workflow_id) queryParams.append("workflow_id", workflow_id);

  const response = await apiRequest<ReportedFeedbackResult>(
    "GET",
    `conversations/issues?${queryParams.toString()}`,
  );

  return response ?? EMPTY_RESULT;
};

export const updateFeedbackStatus = async (
  feedbackId: string,
  status: FeedbackStatus,
): Promise<void> => {
  await apiRequest("PATCH", `conversations/issues/${feedbackId}/status`, {
    status,
  });
};
