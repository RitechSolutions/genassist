import { apiRequest, getApiUrl } from "@/config/api";
import { BackendTranscript } from "@/interfaces/transcript.interface";
import { UserProfile } from "@/interfaces/user.interface";
import { getAccessToken } from "@/services/auth";

const fetchCurrentUserId = async (): Promise<string | null> => {
  try {
    const userProfile = await apiRequest<UserProfile>("GET", "auth/me", undefined);
    return userProfile?.id;
  } catch (error) {
    console.error("Failed to fetch current user ID:", error);
    return null;
  }
};

export const fetchTranscripts = async (): Promise<BackendTranscript[]> => {
  try {
    const userId = await fetchCurrentUserId();
    // let url = "conversations/";
    const url = "conversations/";

    // if (userId) {
    //   url = `conversations/?operator_id=${userId}`;
    // }
    // fix later

    const data = await apiRequest<unknown>(
      "GET",
      url,
      undefined
    );

    if (!data) {
      return [];
    }

    return data as BackendTranscript[];
  } catch (error) {
    console.error("Failed to fetch transcripts:", error);
    return [];
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

  const res = await fetch(url, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  if (!res.ok) {
    throw new Error(`Audio fetch failed (${res.status})`);
  }

  const blob = await res.blob();
  return URL.createObjectURL(blob);
};
