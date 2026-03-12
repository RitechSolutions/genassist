import axios from "axios";
import { getLocalFineTuneApiUrl } from "@/config/localFineTune";
import { getAccessToken } from "@/services/auth";
import type {
  CreateLocalFineTuneJobRequest,
  LocalFineTuneJob,
} from "@/interfaces/localFineTune.interface";

async function localFineTuneRequest<T>(
  method: "GET" | "POST",
  endpoint: string,
  data?: unknown
): Promise<T> {
  const baseURL = getLocalFineTuneApiUrl();
  const url = `${baseURL.replace(/\/$/, "")}/${endpoint.replace(/^\//, "")}`;
  const token = getAccessToken();

  const config: {
    method: "GET" | "POST";
    url: string;
    data?: unknown;
    headers: Record<string, string>;
  } = {
    method,
    url,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  };

  if (data !== undefined && method === "POST") {
    config.data = data;
  }

  const response = await axios.request<T>(config);
  return response.data;
}

export async function listLocalFineTuneJobs(): Promise<LocalFineTuneJob[]> {
  const res = await localFineTuneRequest<LocalFineTuneJob[]>(
    "GET",
    "api/v1/fine-tuning/jobs"
  );
  return Array.isArray(res) ? res : [];
}

export async function getLocalFineTuneJob(id: string): Promise<LocalFineTuneJob | null> {
  try {
    return await localFineTuneRequest<LocalFineTuneJob>(
      "GET",
      `api/v1/fine-tuning/jobs/${id}`
    );
  } catch {
    return null;
  }
}

export async function createLocalFineTuneJob(
  payload: CreateLocalFineTuneJobRequest
): Promise<LocalFineTuneJob> {
  return localFineTuneRequest<LocalFineTuneJob>(
    "POST",
    "api/v1/fine-tuning/jobs",
    payload
  );
}
