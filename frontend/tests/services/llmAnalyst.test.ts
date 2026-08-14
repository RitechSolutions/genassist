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
  getAllLLMAnalysts,
  getLLMAnalyst,
  createLLMAnalyst,
  updateLLMAnalyst,
  deleteLLMAnalyst,
  getAllLLMProviders,
  getAvailableEnrichments,
  getAvailableNodeTypes,
} from "@/services/llmAnalyst";

const mockApiRequest = vi.mocked(apiRequest);
beforeEach(() => vi.clearAllMocks());

describe("getAllLLMAnalysts", () => {
  it("returns the analysts", async () => {
    const analysts = [{ id: "a1" }];
    mockApiRequest.mockResolvedValue(analysts as never);
    expect(await getAllLLMAnalysts()).toBe(analysts);
    expect(mockApiRequest).toHaveBeenCalledWith("GET", "llm-analyst/");
  });

  it("rethrows on error", async () => {
    mockApiRequest.mockRejectedValue(new Error("boom"));
    await expect(getAllLLMAnalysts()).rejects.toThrow("boom");
  });
});

describe("getLLMAnalyst", () => {
  it("returns the analyst", async () => {
    const analyst = { id: "a1" };
    mockApiRequest.mockResolvedValue(analyst as never);
    expect(await getLLMAnalyst("a1")).toBe(analyst);
    expect(mockApiRequest).toHaveBeenCalledWith("GET", "llm-analyst/a1");
  });
});

describe("createLLMAnalyst", () => {
  it("posts a JSON-cloned payload", async () => {
    const data = { name: "x", nested: { a: 1 } } as never;
    const created = { id: "a1" };
    mockApiRequest.mockResolvedValue(created as never);
    expect(await createLLMAnalyst(data)).toBe(created);
    expect(mockApiRequest).toHaveBeenCalledWith("POST", "llm-analyst", {
      name: "x",
      nested: { a: 1 },
    });
  });
});

describe("updateLLMAnalyst", () => {
  it("patches a JSON-cloned payload", async () => {
    const data = { name: "x" } as never;
    const updated = { id: "a1" };
    mockApiRequest.mockResolvedValue(updated as never);
    expect(await updateLLMAnalyst("a1", data)).toBe(updated);
    expect(mockApiRequest).toHaveBeenCalledWith("PATCH", "llm-analyst/a1", { name: "x" });
  });
});

describe("deleteLLMAnalyst", () => {
  it("deletes the analyst", async () => {
    mockApiRequest.mockResolvedValue(undefined as never);
    await deleteLLMAnalyst("a1");
    expect(mockApiRequest).toHaveBeenCalledWith("DELETE", "llm-analyst/a1");
  });

  it("rethrows on error", async () => {
    mockApiRequest.mockRejectedValue(new Error("boom"));
    await expect(deleteLLMAnalyst("a1")).rejects.toThrow("boom");
  });
});

describe("getAllLLMProviders", () => {
  it("returns the providers", async () => {
    const providers = [{ id: "p1" }];
    mockApiRequest.mockResolvedValue(providers as never);
    expect(await getAllLLMProviders()).toBe(providers);
    expect(mockApiRequest).toHaveBeenCalledWith("GET", "llm-providers/");
  });
});

describe("getAvailableEnrichments", () => {
  it("returns the available enrichments", async () => {
    const enrichments = [{ id: "e1" }];
    mockApiRequest.mockResolvedValue(enrichments as never);
    expect(await getAvailableEnrichments()).toBe(enrichments);
    expect(mockApiRequest).toHaveBeenCalledWith("GET", "llm-analyst/available-enrichments");
  });
});

describe("getAvailableNodeTypes", () => {
  it("returns the available node types", async () => {
    const nodeTypes = [{ id: "n1" }];
    mockApiRequest.mockResolvedValue(nodeTypes as never);
    expect(await getAvailableNodeTypes()).toBe(nodeTypes);
    expect(mockApiRequest).toHaveBeenCalledWith("GET", "llm-analyst/available-node-types");
  });
});
