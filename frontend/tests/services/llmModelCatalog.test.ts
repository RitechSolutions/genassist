import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("@/config/api", () => ({
  apiRequest: vi.fn(),
  getApiUrl: vi.fn(async () => "http://localhost/api/"),
  getApiUrlString: "http://localhost/api/",
  formatUploadOrNetworkError: (e: unknown) => (e instanceof Error ? e.message : String(e)),
  API_DEFAULT_TIMEOUT_MS: 1000,
  API_UPLOAD_TIMEOUT_MS: 1000,
  api: { get: vi.fn(), post: vi.fn(), put: vi.fn(), patch: vi.fn(), delete: vi.fn(), request: vi.fn() },
}));

import { apiRequest } from "@/config/api";
import {
  getLlmModelCatalog,
  getLlmModelCatalogProviders,
  createLlmModelCatalogEntry,
  updateLlmModelCatalogEntry,
  deleteLlmModelCatalogEntry,
} from "@/services/llmModelCatalog";

const mockApiRequest = vi.mocked(apiRequest);
beforeEach(() => vi.clearAllMocks());

describe("getLlmModelCatalog", () => {
  it("returns the array from apiRequest", async () => {
    const entries = [{ id: "m1" }];
    mockApiRequest.mockResolvedValue(entries as never);
    const result = await getLlmModelCatalog();
    expect(mockApiRequest).toHaveBeenCalledWith("GET", "llm-model-catalog/");
    expect(result).toBe(entries);
  });

  it("falls back to [] when apiRequest resolves null", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    expect(await getLlmModelCatalog()).toEqual([]);
  });
});

describe("getLlmModelCatalogProviders", () => {
  it("reads the provider types from the /providers endpoint", async () => {
    const providers = [
      { provider_key: "groq", name: "Groq", builtin_model_keys: ["llama2-70b-4096"] },
    ];
    mockApiRequest.mockResolvedValue(providers as never);
    const result = await getLlmModelCatalogProviders();
    expect(mockApiRequest).toHaveBeenCalledWith("GET", "llm-model-catalog/providers");
    expect(result).toBe(providers);
  });

  it("falls back to [] when apiRequest resolves null", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    expect(await getLlmModelCatalogProviders()).toEqual([]);
  });
});

describe("createLlmModelCatalogEntry", () => {
  it("posts the spread payload and returns the created entry", async () => {
    const payload = {
      provider_key: "groq",
      model_key: "llama-3.3-70b-versatile",
      label: "Llama 3.3 70B Versatile",
      is_active: 1,
    };
    const created = { id: "m1", ...payload };
    mockApiRequest.mockResolvedValue(created as never);

    const result = await createLlmModelCatalogEntry(payload);

    expect(mockApiRequest).toHaveBeenCalledWith("POST", "llm-model-catalog/", {
      provider_key: "groq",
      model_key: "llama-3.3-70b-versatile",
      label: "Llama 3.3 70B Versatile",
      is_active: 1,
    });
    expect(result).toBe(created);
  });

  it("sends only the keys it was given, so the server applies its own defaults", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    await createLlmModelCatalogEntry({
      provider_key: "groq",
      model_key: "m",
      label: "M",
    });
    expect(mockApiRequest).toHaveBeenCalledWith("POST", "llm-model-catalog/", {
      provider_key: "groq",
      model_key: "m",
      label: "M",
    });
  });
});

describe("updateLlmModelCatalogEntry", () => {
  it("puts the spread payload to the id endpoint", async () => {
    const payload = { label: "Renamed", is_active: 0 };
    const updated = { id: "m1", ...payload };
    mockApiRequest.mockResolvedValue(updated as never);

    const result = await updateLlmModelCatalogEntry("m1", payload);

    expect(mockApiRequest).toHaveBeenCalledWith("PUT", "llm-model-catalog/m1", {
      label: "Renamed",
      is_active: 0,
    });
    expect(result).toBe(updated);
  });

  it("supports a partial update that touches one field only", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    await updateLlmModelCatalogEntry("m1", { is_active: 1 });
    expect(mockApiRequest).toHaveBeenCalledWith("PUT", "llm-model-catalog/m1", {
      is_active: 1,
    });
  });
});

describe("deleteLlmModelCatalogEntry", () => {
  it("deletes the id endpoint and resolves void", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    await expect(deleteLlmModelCatalogEntry("m1")).resolves.toBeUndefined();
    expect(mockApiRequest).toHaveBeenCalledWith("DELETE", "llm-model-catalog/m1");
  });

  it("propagates a rejection so the dialog can surface it", async () => {
    mockApiRequest.mockRejectedValue(new Error("boom") as never);
    await expect(deleteLlmModelCatalogEntry("m1")).rejects.toThrow("boom");
  });
});
