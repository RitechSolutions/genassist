import { apiRequest } from "@/config/api";
import type {
  LlmModelCatalogCreatePayload,
  LlmModelCatalogEntry,
  LlmModelCatalogProvider,
  LlmModelCatalogUpdatePayload,
} from "@/interfaces/llmModelCatalog.interface";

export async function getLlmModelCatalog(): Promise<LlmModelCatalogEntry[]> {
  const data = await apiRequest<LlmModelCatalogEntry[]>("GET", "llm-model-catalog/");
  return data ?? [];
}

export async function getLlmModelCatalogProviders(): Promise<LlmModelCatalogProvider[]> {
  const data = await apiRequest<LlmModelCatalogProvider[]>(
    "GET",
    "llm-model-catalog/providers"
  );
  return data ?? [];
}

export async function createLlmModelCatalogEntry(
  payload: LlmModelCatalogCreatePayload
): Promise<LlmModelCatalogEntry | null> {
  return await apiRequest<LlmModelCatalogEntry>("POST", "llm-model-catalog/", {
    ...payload,
  });
}

export async function updateLlmModelCatalogEntry(
  id: string,
  payload: LlmModelCatalogUpdatePayload
): Promise<LlmModelCatalogEntry | null> {
  return await apiRequest<LlmModelCatalogEntry>("PUT", `llm-model-catalog/${id}`, {
    ...payload,
  });
}

export async function deleteLlmModelCatalogEntry(id: string): Promise<void> {
  await apiRequest("DELETE", `llm-model-catalog/${id}`);
}
