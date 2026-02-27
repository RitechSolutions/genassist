import { apiRequest, getApiUrl } from "@/config/api";
import { BackendTranscript } from "@/interfaces/transcript.interface";
import { UserProfile } from "@/interfaces/user.interface";
import { getAccessToken } from "@/services/auth";

const fetchCurrentUserId = async (): Promise<string | null> => {
  try {
    const userProfile = await apiRequest<UserProfile>("GET", "auth/me", undefined);
    return userProfile?.id;
  } catch (error) {
    return null;
  }
};

const MAX_BACKEND_LIMIT = 100;

export type FetchTranscriptsResult = {
  items: BackendTranscript[];
  total: number;
  page: number;
  page_size: number;
  has_more: boolean;
};

interface PaginatedConversationsResponse {
  items: BackendTranscript[];
  total: number;
  page: number;
  page_size: number;
  has_more: boolean;
}

export const fetchTranscripts = async (
  limit?: number,
  skip?: number,
  sentiment?: string,
  hostility_neutral_max?: number,
  hostility_positive_max?: number,
  include_feedback?: boolean,
  conversation_status?: string[],
  order_by?: string,
  sort_direction?: string
): Promise<FetchTranscriptsResult> => {
  try {
    let url = "conversations/";

    // Clamp limit to backend maximum
    const safeLimit =
      typeof limit === "number" && limit > 0
        ? Math.min(limit, MAX_BACKEND_LIMIT)
        : 20; // Default to 20 if not specified

    // Add pagination and filter parameters
    const queryParams = new URLSearchParams();
    if (skip) queryParams.append("skip", String(skip));
    queryParams.append("limit", String(safeLimit));
    if (sentiment && sentiment !== "all") queryParams.append("sentiment", sentiment);
    if (hostility_neutral_max !== undefined)
      queryParams.append("hostility_neutral_max", String(hostility_neutral_max));
    if (hostility_positive_max !== undefined)
      queryParams.append("hostility_positive_max", String(hostility_positive_max));
    if (typeof include_feedback === "boolean")
      queryParams.append("include_feedback", String(include_feedback));
    if (conversation_status && conversation_status.length > 0) {
      conversation_status.forEach((status) => {
        queryParams.append("conversation_status", status);
      });
    }
    if (order_by) queryParams.append("order_by", order_by);
    if (sort_direction) queryParams.append("sort_direction", sort_direction);

    if (queryParams.toString()) {
      url += `?${queryParams.toString()}`;
    }

    const response = await apiRequest<PaginatedConversationsResponse>(
      "GET",
      url,
      undefined
    );

    if (!response) {
      return { items: [], total: 0, page: 1, page_size: safeLimit, has_more: false };
    }

    return {
      items: response.items || [],
      total: response.total || 0,
      page: response.page || 1,
      page_size: response.page_size || safeLimit,
      has_more: response.has_more || false,
    };
  } catch (error) {
    return { items: [], total: 0, page: 1, page_size: 20, has_more: false };
  }
};

export const fetchTranscript = async (
  id: string
): Promise<BackendTranscript | null> => {
  try {
    const data = await apiRequest<BackendTranscript>(
      "GET",
      `audio/recordings/${id}`,
      undefined
    );
    if (!data) return null;

    return data;
  } catch (error) {
    return null;
  }
};

export const getAudioUrl = async (recordingId: string): Promise<string> => {
  const baseURL = await getApiUrl();
  const url     = `${baseURL}audio/files/${recordingId}`;
  const token   = getAccessToken();

  if (!token) {
    throw new Error("Not authenticated—no access token found");
  }

  const headers: Record<string, string> = {
    Authorization: `Bearer ${token}`,
  };

  const tenantId = localStorage.getItem("tenant_id");
  if (tenantId) {
    headers["x-tenant-id"] = tenantId;
  }

  const res = await fetch(url, { headers });

  if (!res.ok) {
    throw new Error(`Audio fetch failed (${res.status})`);
  }

  const blob = await res.blob();
  return URL.createObjectURL(blob);
};

export interface ConversationFeedback {
  feedback: "good" | "bad";
  feedback_message: string;
  feedback_user_id: string;
  feedback_timestamp: string;
}

export const submitMessageFeedback = async (
  messageId: string,
  feedback: "good" | "bad",
  feedbackMessage?: string
): Promise<boolean> => {
  try {
    const payload = {
      message_id: messageId,
      feedback,
      feedback_message: feedbackMessage ?? "",
    };

    await apiRequest(
      "PATCH",
      `/conversations/message/add-feedback/${messageId}`,
      payload
    );
    return true;
  } catch (e) {
    return false;
  }
};

export const submitConversationFeedback = async (
  conversationId: string,
  feedback: "good" | "bad",
  feedbackMessage: string
): Promise<boolean> => {
  try {
    const userId = await fetchCurrentUserId();
    if (!userId) {
      throw new Error("Unable to get current user ID");
    }

    const feedbackEntry = {
      feedback,
      feedback_message: feedbackMessage,
      feedback_user_id: userId,
      feedback_timestamp: new Date().toISOString(),
    };

    await apiRequest(
      "PATCH",
      `/conversations/feedback/${conversationId}`,
      feedbackEntry
    );

    return true;
  } catch (error) {
    return false;
  }
};

export interface AgentResponseLog {
  // Shape is backend-defined; keep flexible on the frontend.
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  [key: string]: any;
}

export const fetchAgentResponseLog = async (
  messageId: string
): Promise<AgentResponseLog | null> => {
  try {
    const data = await apiRequest<AgentResponseLog>(
      "GET",
      `/conversations/message/agent-response-log/${messageId}`,
      undefined
    );
    if (!data) {
      return null;
    }
    return data;
  } catch (error) {
    return null;
  }
};
