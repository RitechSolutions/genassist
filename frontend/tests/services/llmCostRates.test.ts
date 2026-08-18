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
  getLlmCostRates,
  createLlmCostRate,
  updateLlmCostRate,
  deleteLlmCostRate,
} from "@/services/llmCostRates";

const mockApiRequest = vi.mocked(apiRequest);
beforeEach(() => vi.clearAllMocks());

// SKIPPED: importLlmCostRatesCsv / exportLlmCostRatesCsv use fetch() + FormData +
// localStorage + Blob (browser-only), so they are out of scope for these node tests.

describe("getLlmCostRates", () => {
  it("returns the array from apiRequest", async () => {
    const rates = [{ id: "r1" }];
    mockApiRequest.mockResolvedValue(rates as never);
    const result = await getLlmCostRates();
    expect(mockApiRequest).toHaveBeenCalledWith("GET", "llm-cost-rates/");
    expect(result).toBe(rates);
  });

  it("falls back to [] when apiRequest resolves null", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    expect(await getLlmCostRates()).toEqual([]);
  });
});

describe("createLlmCostRate", () => {
  it("posts the spread payload and returns the created rate", async () => {
    const payload = { provider: "openai", model: "gpt-4" };
    const created = { id: "r1", ...payload };
    mockApiRequest.mockResolvedValue(created as never);
    const result = await createLlmCostRate(payload as never);
    expect(mockApiRequest).toHaveBeenCalledWith("POST", "llm-cost-rates/", {
      provider: "openai",
      model: "gpt-4",
    });
    expect(result).toBe(created);
  });
});

describe("updateLlmCostRate", () => {
  it("puts the spread payload to the id endpoint", async () => {
    const payload = { input_cost_per_million: 5 };
    const updated = { id: "r1", ...payload };
    mockApiRequest.mockResolvedValue(updated as never);
    const result = await updateLlmCostRate("r1", payload as never);
    expect(mockApiRequest).toHaveBeenCalledWith("PUT", "llm-cost-rates/r1", {
      input_cost_per_million: 5,
    });
    expect(result).toBe(updated);
  });
});

describe("deleteLlmCostRate", () => {
  it("deletes the id endpoint", async () => {
    mockApiRequest.mockResolvedValue(undefined as never);
    await deleteLlmCostRate("r1");
    expect(mockApiRequest).toHaveBeenCalledWith("DELETE", "llm-cost-rates/r1");
  });
});
