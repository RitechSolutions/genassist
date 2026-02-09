import { apiRequest, getApiUrl } from "@/config/api";
import { normalizeTranscriptList } from "@/helpers/pagination";
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
};

export const fetchTranscripts = async (
  limit?: number,
  skip?: number,
  sentiment?: string,
  hostility_neutral_max?: number,
  hostility_positive_max?: number,
  include_feedback?: boolean
): Promise<FetchTranscriptsResult> => {
  try {
    const userId = await fetchCurrentUserId();
    let url = "conversations/";

    // Clamp limit to backend maximum
    const safeLimit =
      typeof limit === "number" && limit > 0
        ? Math.min(limit, MAX_BACKEND_LIMIT)
        : undefined;

    // Add pagination and filter parameters
    const queryParams = new URLSearchParams();
    if (skip) queryParams.append("skip", String(skip));
    if (typeof safeLimit === "number") {
      queryParams.append("limit", String(safeLimit));
    }
    if (sentiment && sentiment !== "all") queryParams.append("sentiment", sentiment);
    if (hostility_neutral_max !== undefined)
      queryParams.append("hostility_neutral_max", String(hostility_neutral_max));
    if (hostility_positive_max !== undefined)
      queryParams.append("hostility_positive_max", String(hostility_positive_max));
    if (typeof include_feedback === "boolean")
      queryParams.append("include_feedback", String(include_feedback));
    
    if (queryParams.toString()) {
      url += `?${queryParams.toString()}`;
    }

    // if (userId) {
    //   url = `conversations/?operator_id=${userId}`;
    // }
    // fix later

    const data = await apiRequest<unknown>(
      "GET",
      url,
      undefined
    );

    const normalized = normalizeTranscriptList(data);
    const baseCount =
      typeof skip === "number" && skip > 0
        ? skip + normalized.items.length
        : normalized.items.length;
    const optimisticTotal =
      typeof safeLimit === "number" && normalized.items.length === safeLimit
        ? baseCount + safeLimit
        : baseCount;
    const inferredTotal = Math.max(normalized.total, optimisticTotal);

    return {
      items: normalized.items,
      total: inferredTotal,
    };
  } catch (error) {
    return { items: [], total: 0 };
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
