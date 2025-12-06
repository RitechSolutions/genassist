import { getApiUrl, api } from "@/config/api";
import { AudioAnalysisResponse } from "@/interfaces/audio-upload.interface";

type UploadResponse = {
  success: boolean;
  message?: string;
  transcriptId?: string;
  analysisData?: AudioAnalysisResponse;
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
    
    const response = await api.post(`${baseURL}audio/analyze_recording`, formData, {
      headers: {
        "Content-Type": "multipart/form-data",
        Accept: "application/json",
      },
    });

    const responseData = response.data as AudioAnalysisResponse;
    
    if (responseData && responseData.id && responseData.conversation_id) {
      return {
        success: true,
        message: "Audio analyzed successfully",
        transcriptId: responseData.conversation_id,
        analysisData: responseData,
      };
    } else {
      throw new Error("Invalid response structure from server");
    }

  } catch (error) {
    if (error.response) {
      const errorData = error.response.data;
      let errorMessage;
      
      if (typeof errorData === 'string') {
        errorMessage = errorData;
      } else if (errorData && (errorData.error || errorData.message || errorData.detail)) {
        errorMessage = errorData.error || errorData.message || errorData.detail;
      } else {
        errorMessage = `HTTP error ${error.response.status}`;
      }
      
      throw new Error(`Upload failed: ${errorMessage}`);
    } else if (error.request) {
      throw new Error('Network error: Unable to reach the server');
    } else {
      throw new Error(error.message || 'Unknown error occurred');
    }
  }
}
