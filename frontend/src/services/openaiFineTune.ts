import { apiRequest, api, getApiUrl } from "@/config/api";
import type {
  CreateFineTuneJobRequest,
  FineTuneJob,
  OpenAIFileItem,
  PaginatedResponse,
} from "@/interfaces/fineTune.interface";

function normalizeList<T>(res: T[] | PaginatedResponse<T> | null): T[] {
  if (!res) return [];
  if (Array.isArray(res)) return res;
  if (typeof res === "object" && (res as PaginatedResponse<T>).data) {
    return (res as PaginatedResponse<T>).data || [];
  }
  return [];
}

export async function getFineTunableModels(): Promise<string[]> {
  const res = await apiRequest<string[] | PaginatedResponse<string>>(
    "GET",
    "openai/models/fine-tunable"
  );
  return normalizeList<string>(res);
}

export async function listFineTuneJobs(): Promise<FineTuneJob[]> {
  const res = await apiRequest<FineTuneJob[] | PaginatedResponse<FineTuneJob>>(
    "GET",
    "openai/fine-tuning/jobs?sync=True"
  );
  return normalizeList<FineTuneJob>(res);
}

export async function getFineTuneJob(
  id: string,
  sync: boolean = true
): Promise<FineTuneJob | null> {
  return apiRequest<FineTuneJob>(
    "GET",
    `openai/fine-tuning/jobs/${id}${sync ? "?sync=True" : ""}`
  );
}

export async function createFineTuneJob(
  payload: CreateFineTuneJobRequest
): Promise<FineTuneJob> {
  return apiRequest<FineTuneJob>(
    "POST",
    "openai/fine-tuning/jobs",
    JSON.parse(JSON.stringify(payload))
  );
}

export async function cancelFineTuneJob(id: string): Promise<{ status?: string } | null> {
  return apiRequest<{ status?: string }>(
    "POST",
    `openai/fine-tuning/jobs/${id}/cancel`
  );
}

export async function uploadFineTuneFile(
  file: File,
  purpose: string = "fine-tune"
): Promise<OpenAIFileItem> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("purpose", purpose);

  const baseURL = await getApiUrl();
  const url = `${baseURL}openai/upload`;

  const response = await api.request<OpenAIFileItem>({
    method: "POST",
    url,
    data: formData,
    headers: { "Content-Type": "multipart/form-data" },
  });

  return response.data;
}

export async function listOpenAIFiles(): Promise<OpenAIFileItem[]> {
  const res = await apiRequest<OpenAIFileItem[] | PaginatedResponse<OpenAIFileItem>>(
    "GET",
    "openai/files"
  );
  return normalizeList<OpenAIFileItem>(res);
}