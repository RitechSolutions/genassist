import { getApiUrl, apiRequest } from "@/config/api";
import type {
  LlmCostRate,
  LlmCostRateImportResult,
} from "@/interfaces/llmCostRate.interface";

export async function getLlmCostRates(): Promise<LlmCostRate[]> {
  const data = await apiRequest<LlmCostRate[]>("GET", "llm-cost-rates/");
  return data ?? [];
}

export async function importLlmCostRatesCsv(
  file: File
): Promise<LlmCostRateImportResult> {
  const baseURL = (await getApiUrl()).replace(/\/$/, "");
  const fullUrl = `${baseURL}/llm-cost-rates/import`;

  const token = localStorage.getItem("access_token");
  const tokenType = localStorage.getItem("token_type") || "Bearer";
  const tenantId = localStorage.getItem("tenant_id");

  const headers: Record<string, string> = {};
  if (token) {
    headers.Authorization = `${tokenType} ${token}`;
  }
  if (tenantId) {
    headers["x-tenant-id"] = tenantId;
  }

  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(fullUrl, {
    method: "POST",
    body: formData,
    headers,
  });

  if (!response.ok) {
    const errBody = (await response.json().catch(() => ({}))) as {
      detail?: string;
    };
    throw new Error(errBody.detail || `Import failed (${response.status})`);
  }

  return (await response.json()) as LlmCostRateImportResult;
}

export async function deleteLlmCostRate(id: string): Promise<void> {
  await apiRequest("DELETE", `llm-cost-rates/${id}`);
}

export async function exportLlmCostRatesCsv(): Promise<Blob> {
  const baseURL = (await getApiUrl()).replace(/\/$/, "");
  const fullUrl = `${baseURL}/llm-cost-rates/export`;

  const token = localStorage.getItem("access_token");
  const tokenType = localStorage.getItem("token_type") || "Bearer";
  const tenantId = localStorage.getItem("tenant_id");

  const headers: Record<string, string> = {};
  if (token) {
    headers.Authorization = `${tokenType} ${token}`;
  }
  if (tenantId) {
    headers["x-tenant-id"] = tenantId;
  }

  const response = await fetch(fullUrl, { method: "GET", headers });
  if (!response.ok) {
    const errBody = (await response.json().catch(() => ({}))) as {
      detail?: string;
    };
    throw new Error(errBody.detail || `Export failed (${response.status})`);
  }
  return await response.blob();
}
