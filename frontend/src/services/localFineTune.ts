import { AxiosError } from "axios";
import { apiRequest } from "@/config/api";
import type {
  CreateDeploymentRequest,
  CreateLocalFineTuneJobRequest,
  DeleteJobFilesRequest,
  DeleteJobFilesResponse,
  GpuInfo,
  SystemGpusResponse,
  LocalFineTuneDeployment,
  LocalFineTuneDeploymentHealth,
  LocalFineTuneJob,
  LocalFineTuneJobEvent,
  LocalFineTuneSupportedModel,
  DeploymentStopResponse,
} from "@/interfaces/localFineTune.interface";

const BASE = "local-fine-tuning";

/** Pull a human-readable message out of an error from the local-fine-tune proxy.
 *  The proxy mirrors the backend AppException shape (error / error_detail), so
 *  prefer those, then fall back to common FastAPI fields and finally the
 *  axios error message. */
export function getLocalFineTuneErrorMessage(err: unknown, fallback: string): string {
  if (err instanceof AxiosError) {
    const data = err.response?.data as
      | { error_detail?: string; error?: string; detail?: string; message?: string }
      | undefined;
    const detail = data?.error_detail || data?.error || data?.detail || data?.message;
    if (detail) return detail;
    if (err.message) return err.message;
  } else if (err instanceof Error && err.message) {
    return err.message;
  }
  return fallback;
}

export async function listLocalFineTuneSupportedModels(
  skip = 0,
  limit = 10
): Promise<LocalFineTuneSupportedModel[]> {
  const data = await apiRequest<LocalFineTuneSupportedModel[]>(
    "GET",
    `${BASE}/supported-models`,
    undefined,
    { params: { skip, limit } }
  );
  return Array.isArray(data) ? data : [];
}

export async function listLocalFineTuneJobs(): Promise<LocalFineTuneJob[]> {
  const data = await apiRequest<LocalFineTuneJob[]>("GET", `${BASE}/jobs`);
  return Array.isArray(data) ? data : [];
}

export async function getLocalFineTuneJob(id: string): Promise<LocalFineTuneJob | null> {
  try {
    return await apiRequest<LocalFineTuneJob>("GET", `${BASE}/jobs/${id}`);
  } catch {
    return null;
  }
}

export async function listLocalFineTuneJobEvents(
  jobId: string
): Promise<LocalFineTuneJobEvent[]> {
  try {
    const data = await apiRequest<LocalFineTuneJobEvent[]>(
      "GET",
      `${BASE}/jobs/${jobId}/events`
    );
    return Array.isArray(data) ? data : [];
  } catch {
    return [];
  }
}

export async function createLocalFineTuneJob(
  payload: CreateLocalFineTuneJobRequest
): Promise<LocalFineTuneJob> {
  const result = await apiRequest<LocalFineTuneJob>(
    "POST",
    `${BASE}/jobs`,
    payload as unknown as Record<string, unknown>
  );
  if (!result) throw new Error("Failed to create local fine-tune job");
  return result;
}

export async function cancelLocalFineTuneJob(jobId: string): Promise<LocalFineTuneJob> {
  const result = await apiRequest<LocalFineTuneJob>(
    "POST",
    `${BASE}/jobs/${jobId}/cancel`
  );
  if (!result) throw new Error("Failed to cancel local fine-tune job");
  return result;
}

export async function deleteLocalFineTuneJobFiles(
  jobId: string,
  options: DeleteJobFilesRequest = {}
): Promise<DeleteJobFilesResponse> {
  const { delete_data_files = true, delete_checkpoints = true, delete_model = false } = options;
  const result = await apiRequest<DeleteJobFilesResponse>(
    "DELETE",
    `${BASE}/jobs/${jobId}/files`,
    undefined,
    { params: { delete_data_files, delete_checkpoints, delete_model } }
  );
  if (!result) throw new Error("Failed to delete local fine-tune job files");
  return result;
}

export async function createDeployment(
  payload: CreateDeploymentRequest
): Promise<LocalFineTuneDeployment> {
  const result = await apiRequest<LocalFineTuneDeployment>(
    "POST",
    `${BASE}/deployments`,
    payload as unknown as Record<string, unknown>
  );
  if (!result) throw new Error("Failed to create deployment");
  return result;
}

export async function listDeployments(): Promise<LocalFineTuneDeployment[]> {
  const data = await apiRequest<LocalFineTuneDeployment[]>("GET", `${BASE}/deployments`);
  return Array.isArray(data) ? data : [];
}

export async function getDeployment(id: string): Promise<LocalFineTuneDeployment | null> {
  try {
    return await apiRequest<LocalFineTuneDeployment>("GET", `${BASE}/deployments/${id}`);
  } catch {
    return null;
  }
}

export async function stopDeployment(id: string): Promise<DeploymentStopResponse> {
  const result = await apiRequest<DeploymentStopResponse>(
    "DELETE",
    `${BASE}/deployments/${id}`
  );
  if (!result) throw new Error("Failed to stop deployment");
  return result;
}

export async function checkDeploymentHealth(id: string): Promise<LocalFineTuneDeploymentHealth> {
  const result = await apiRequest<LocalFineTuneDeploymentHealth>(
    "GET",
    `${BASE}/deployments/${id}/health`
  );
  if (!result) throw new Error("Failed to fetch deployment health");
  return result;
}

export async function listSystemGpus(): Promise<GpuInfo[]> {
  const res = await apiRequest<SystemGpusResponse>("GET", `${BASE}/system/gpus`);
  if (!res) return [];
  return res.cuda_available ? res.gpus : [];
}

export async function testDeploymentInference(
  deploymentId: string,
  message: string
): Promise<string> {
  const result = await apiRequest<{ content: string }>(
    "POST",
    `${BASE}/deployments/${deploymentId}/test-inference`,
    { message }
  );
  if (!result) throw new Error("Inference call failed");
  return result.content;
}