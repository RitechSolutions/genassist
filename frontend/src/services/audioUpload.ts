import { getApiUrl } from "@/config/api";

type UploadResponse = {
  success: boolean;
  message?: string;
  transcriptId?: string;
};

export async function uploadAudio(
  file: File,
  agentId: string
): Promise<UploadResponse> {
  const formData = new FormData();
  const recordedAt = new Date().toISOString().split(".")[0] + "Z";

  formData.append("file", file);
  formData.append("operator_id", agentId);
  formData.append("transcription_model_name", "base.en");
  formData.append("llm_model", "gpt-4o");
  formData.append("recorded_at", recordedAt);

  try {
    const baseURL = await getApiUrl();
    
    const token = localStorage.getItem('access_token');
    const tokenType = localStorage.getItem('token_type') || 'Bearer';
    
    if (!token) {
      throw new Error('Authentication token not found. Please log in again.');
    }

    const response = await fetch(`${baseURL}audio/analyze_recording`, {
      method: "POST",
      body: formData,
      headers: {
        Accept: "application/json",
        Authorization: `${tokenType} ${token}`,
      },
      credentials: 'include',
    });

    if (!response.ok) {
      const errorData = await response.text();
      let errorMessage;
      try {
        const parsedError = JSON.parse(errorData);
        errorMessage = parsedError.error || parsedError.message || 'Unknown error occurred';
      } catch {
        errorMessage = errorData || `HTTP error ${response.status}`;
      }
      throw new Error(`Upload failed: ${errorMessage}`);
    }

    return (await response.json()) as UploadResponse;
  } catch (error) {
    console.error("Upload error:", error);
    throw error;
  }
}
