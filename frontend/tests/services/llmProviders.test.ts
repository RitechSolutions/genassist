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
  getAllLLMProviders,
  getLLMProvidersMinimal,
  getLLMProvider,
  createLLMProvider,
  updateLLMProvider,
  deleteLLMProvider,
  getLLMProvidersFormSchemas,
  testLLMProviderConnection,
} from "@/services/llmProviders";

const mockApiRequest = vi.mocked(apiRequest);
beforeEach(() => vi.clearAllMocks());

describe("getAllLLMProviders", () => {
  it("returns the providers", async () => {
    const providers = [{ id: "p1" }];
    mockApiRequest.mockResolvedValue(providers as never);
    expect(await getAllLLMProviders()).toBe(providers);
    expect(mockApiRequest).toHaveBeenCalledWith("GET", "llm-providers/");
  });

  it("rethrows on error", async () => {
    mockApiRequest.mockRejectedValue(new Error("boom"));
    await expect(getAllLLMProviders()).rejects.toThrow("boom");
  });
});

describe("getLLMProvidersMinimal", () => {
  it("returns the minimal providers", async () => {
    const providers = [{ id: "p1" }];
    mockApiRequest.mockResolvedValue(providers as never);
    expect(await getLLMProvidersMinimal()).toBe(providers);
    expect(mockApiRequest).toHaveBeenCalledWith("GET", "llm-providers/minimal");
  });
});

describe("getLLMProvider", () => {
  it("returns the provider", async () => {
    const provider = { id: "p1" };
    mockApiRequest.mockResolvedValue(provider as never);
    expect(await getLLMProvider("p1")).toBe(provider);
    expect(mockApiRequest).toHaveBeenCalledWith("GET", "llm-providers/p1");
  });
});

describe("createLLMProvider", () => {
  it("posts a JSON-cloned payload", async () => {
    const providerData = { name: "x", config: { a: 1 } } as never;
    const created = { id: "p1" };
    mockApiRequest.mockResolvedValue(created as never);
    expect(await createLLMProvider(providerData)).toBe(created);
    expect(mockApiRequest).toHaveBeenCalledWith("POST", "llm-providers", {
      name: "x",
      config: { a: 1 },
    });
  });
});

describe("updateLLMProvider", () => {
  it("patches a JSON-cloned payload", async () => {
    const providerData = { name: "x" } as never;
    const updated = { id: "p1" };
    mockApiRequest.mockResolvedValue(updated as never);
    expect(await updateLLMProvider("p1", providerData)).toBe(updated);
    expect(mockApiRequest).toHaveBeenCalledWith("PATCH", "llm-providers/p1", { name: "x" });
  });
});

describe("deleteLLMProvider", () => {
  it("deletes the provider", async () => {
    mockApiRequest.mockResolvedValue(undefined as never);
    await deleteLLMProvider("p1");
    expect(mockApiRequest).toHaveBeenCalledWith("DELETE", "llm-providers/p1");
  });

  it("rethrows on error", async () => {
    mockApiRequest.mockRejectedValue(new Error("boom"));
    await expect(deleteLLMProvider("p1")).rejects.toThrow("boom");
  });
});

describe("getLLMProvidersFormSchemas", () => {
  it("fetches the form schemas", async () => {
    const schema = { fields: [] };
    mockApiRequest.mockResolvedValue(schema as never);
    expect(await getLLMProvidersFormSchemas()).toBe(schema);
    expect(mockApiRequest).toHaveBeenCalledWith("GET", "llm-providers/form_schemas");
  });
});

describe("testLLMProviderConnection", () => {
  it("posts without a provider_id query when none is given", async () => {
    const result = { success: true, message: "ok" };
    mockApiRequest.mockResolvedValue(result as never);
    const res = await testLLMProviderConnection("openai", { api_key: "k" });
    expect(res).toBe(result);
    expect(mockApiRequest).toHaveBeenCalledWith("POST", "llm-providers/test-connection", {
      llm_model_provider: "openai",
      connection_data: { api_key: "k" },
    });
  });

  it("appends the provider_id query when given", async () => {
    mockApiRequest.mockResolvedValue({ success: true, message: "ok" } as never);
    await testLLMProviderConnection("openai", { api_key: "k" }, "p1");
    expect(mockApiRequest).toHaveBeenCalledWith(
      "POST",
      "llm-providers/test-connection?provider_id=p1",
      { llm_model_provider: "openai", connection_data: { api_key: "k" } }
    );
  });
});
