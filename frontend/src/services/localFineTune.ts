import axios from "axios";
import { getLocalFineTuneApiUrl } from "@/config/localFineTune";
import { getAccessToken, getTenantId } from "@/services/auth";
import type {
  CreateLocalFineTuneJobRequest,
  LocalFineTuneJob,
  LocalFineTuneJobEvent,
  LocalFineTuneSupportedModel,
} from "@/interfaces/localFineTune.interface";

async function localFineTuneRequest<T>(
  method: "GET" | "POST",
  endpoint: string,
  options?: { data?: unknown; params?: Record<string, string | number | boolean> }
): Promise<T> {
  const baseURL = getLocalFineTuneApiUrl();
  const path = `${baseURL.replace(/\/$/, "")}/${endpoint.replace(/^\//, "")}`;
  const token = getAccessToken();
  const tokenType = localStorage.getItem("token_type") || "Bearer";
  const properTokenType =
    tokenType.toLowerCase() === "bearer" ? "Bearer" : tokenType;
  const tenantId = getTenantId();

  const config: {
    method: "GET" | "POST";
    url: string;
    data?: unknown;
    params?: Record<string, string | number | boolean>;
    headers: Record<string, string>;
  } = {
    method,
    url: path,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `${properTokenType} ${token}` } : {}),
      ...(tenantId ? { "x-tenant-id": tenantId } : {}),
    },
  };

  if (options?.params !== undefined) {
    config.params = options.params;
  }

  if (options?.data !== undefined && method === "POST") {
    config.data = options.data;
  }

  const response = await axios.request<T>(config);
  return response.data;
}

function normalizeSupportedModelItem(
  item: unknown
): LocalFineTuneSupportedModel | null {
  if (!item || typeof item !== "object") return null;
  const o = item as Record<string, unknown>;
  const id = o.id != null ? String(o.id) : "";
  if (!id) return null;
  const label =
    o.name ??
    o.display_name ??
    o.model_name ??
    o.model ??
    o.title ??
    id;
  return { id, name: String(label) };
}

function normalizeSupportedModelsResponse(
  raw: unknown
): LocalFineTuneSupportedModel[] {
  if (Array.isArray(raw)) {
    return raw
      .map(normalizeSupportedModelItem)
      .filter((m): m is LocalFineTuneSupportedModel => m !== null);
  }
  if (raw && typeof raw === "object") {
    const o = raw as Record<string, unknown>;
    const list = o.items ?? o.data ?? o.results ?? o.models ?? o.rows;
    if (Array.isArray(list)) {
      return list
        .map(normalizeSupportedModelItem)
        .filter((m): m is LocalFineTuneSupportedModel => m !== null);
    }
  }
  return [];
}

export async function listLocalFineTuneSupportedModels(
  skip = 0,
  limit = 10
): Promise<LocalFineTuneSupportedModel[]> {
  const res = await localFineTuneRequest<unknown>("GET", "api/v1/supported-models", {
    params: { skip, limit },
  });
  return normalizeSupportedModelsResponse(res);
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

export async function listLocalFineTuneJobEvents(
  jobId: string
): Promise<LocalFineTuneJobEvent[]> {
  try {
    const res = await localFineTuneRequest<LocalFineTuneJobEvent[]>(
      "GET",
      `api/v1/fine-tuning/jobs/${jobId}/events`
    );
    return Array.isArray(res) ? res : [];
  } catch {
    return [];
  }
}

export async function createLocalFineTuneJob(
  payload: CreateLocalFineTuneJobRequest
): Promise<LocalFineTuneJob> {
  return localFineTuneRequest<LocalFineTuneJob>("POST", "api/v1/fine-tuning/jobs", {
    data: payload,
  });
}
