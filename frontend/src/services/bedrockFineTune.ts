import { apiRequest, api, getApiUrl } from "@/config/api";
import type { PaginatedResponse } from "@/interfaces/fineTune.interface";
import type {
  BedrockFineTuneJob,
  BedrockGenerateUploadResult,
  BedrockUploadResult,
  CreateBedrockFineTuneJobRequest,
} from "@/interfaces/bedrockFineTune.interface";

function normalizeList<T>(res: T[] | PaginatedResponse<T> | null): T[] {
  if (!res) return [];
  if (Array.isArray(res)) return res;
  if (typeof res === "object" && (res as PaginatedResponse<T>).data) {
    return (res as PaginatedResponse<T>).data || [];
  }
  return [];
}

export async function getBedrockFineTunableModels(): Promise<string[]> {
  const res = await apiRequest<string[] | PaginatedResponse<string>>(
    "GET",
    "bedrock/models/fine-tunable"
  );
  return normalizeList<string>(res);
}

export async function listBedrockFineTuneJobs(): Promise<BedrockFineTuneJob[]> {
  const res = await apiRequest<BedrockFineTuneJob[] | PaginatedResponse<BedrockFineTuneJob>>(
    "GET",
    "bedrock/fine-tuning/jobs"
  );
  return normalizeList<BedrockFineTuneJob>(res);
}

// Syncs each active job with Bedrock, then returns the refreshed list.
// This is the only entry point that triggers a sync — the Sync button calls it.
export async function syncBedrockFineTuneJobs(): Promise<BedrockFineTuneJob[]> {
  const res = await apiRequest<BedrockFineTuneJob[] | PaginatedResponse<BedrockFineTuneJob>>(
    "POST",
    "bedrock/fine-tuning/jobs/sync"
  );
  return normalizeList<BedrockFineTuneJob>(res);
}

export async function getBedrockFineTuneJob(
  id: string,
  sync: boolean = true
): Promise<BedrockFineTuneJob | null> {
  return apiRequest<BedrockFineTuneJob>(
    "GET",
    `bedrock/fine-tuning/jobs/${id}${sync ? "?sync=True" : ""}`
  );
}

export async function createBedrockFineTuneJob(
  payload: CreateBedrockFineTuneJobRequest
): Promise<BedrockFineTuneJob> {
  return apiRequest<BedrockFineTuneJob>(
    "POST",
    "bedrock/fine-tuning/jobs",
    JSON.parse(JSON.stringify(payload))
  );
}

export async function cancelBedrockFineTuneJob(
  id: string
): Promise<BedrockFineTuneJob | null> {
  return apiRequest<BedrockFineTuneJob>(
    "POST",
    `bedrock/fine-tuning/jobs/${id}/cancel`
  );
}

export async function deployBedrockCustomModel(
  id: string
): Promise<BedrockFineTuneJob | null> {
  return apiRequest<BedrockFineTuneJob>(
    "POST",
    `bedrock/fine-tuning/jobs/${id}/deploy`
  );
}

export async function uploadBedrockTrainingData(
  file: File
): Promise<BedrockUploadResult> {
  const formData = new FormData();
  formData.append("file", file);

  const baseURL = await getApiUrl();
  const url = `${baseURL}bedrock/upload`;

  const response = await api.request<BedrockUploadResult>({
    method: "POST",
    url,
    data: formData,
    headers: { "Content-Type": "multipart/form-data" },
  });

  return response.data;
}

export async function generateBedrockTrainingFileFromConversations(payload: {
  conversation_ids: string[];
}): Promise<BedrockGenerateUploadResult> {
  const res = await apiRequest<BedrockGenerateUploadResult>(
    "POST",
    "bedrock/fine-tuning/generate-from-conversations",
    { ...payload, upload_to_s3: true }
  );
  return res as BedrockGenerateUploadResult;
}

export async function downloadBedrockGeneratedTrainingFile(payload: {
  conversation_ids: string[];
}): Promise<Blob> {
  const baseURL = await getApiUrl();
  const url = `${baseURL}bedrock/fine-tuning/generate-from-conversations`;
  const response = await api.request<Blob>({
    method: "POST",
    url,
    data: { ...payload, upload_to_s3: false },
    responseType: "blob",
  });
  return response.data;
}
