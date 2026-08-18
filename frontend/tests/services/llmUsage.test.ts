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
  fetchLlmUsageSummary,
  fetchLlmUsageBreakdown,
  fetchLlmUsageTimeseries,
  fetchLlmUsageFilterOptions,
} from "@/services/llmUsage";

const mockApiRequest = vi.mocked(apiRequest);
beforeEach(() => vi.clearAllMocks());

describe("fetchLlmUsageSummary", () => {
  it("hits the summary endpoint with no query when no params", async () => {
    const resp = { total_cost_usd: 1 };
    mockApiRequest.mockResolvedValue(resp as never);
    const result = await fetchLlmUsageSummary();
    expect(mockApiRequest).toHaveBeenCalledWith("get", "/analytics/llm-usage/summary");
    expect(result).toBe(resp);
  });

  it("builds the query string from filters", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    await fetchLlmUsageSummary({ agent_id: "a1", model: "gpt" });
    expect(mockApiRequest).toHaveBeenCalledWith(
      "get",
      "/analytics/llm-usage/summary?agent_id=a1&model=gpt"
    );
  });

  it("propagates rejections", async () => {
    mockApiRequest.mockRejectedValue(new Error("boom"));
    await expect(fetchLlmUsageSummary()).rejects.toThrow("boom");
  });
});

describe("fetchLlmUsageBreakdown", () => {
  it("puts the dimension first in the query string", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    await fetchLlmUsageBreakdown("agent", { agent_id: "a1" });
    expect(mockApiRequest).toHaveBeenCalledWith(
      "get",
      "/analytics/llm-usage/breakdown?dimension=agent&agent_id=a1"
    );
  });

  it("includes only the dimension when no other params", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    await fetchLlmUsageBreakdown("model");
    expect(mockApiRequest).toHaveBeenCalledWith(
      "get",
      "/analytics/llm-usage/breakdown?dimension=model"
    );
  });
});

describe("fetchLlmUsageTimeseries", () => {
  it("builds the timeseries query string", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    await fetchLlmUsageTimeseries({ from_date: "2025-01-01" });
    expect(mockApiRequest).toHaveBeenCalledWith(
      "get",
      "/analytics/llm-usage/timeseries?from_date=2025-01-01"
    );
  });
});

describe("fetchLlmUsageFilterOptions", () => {
  it("hits the filter-options endpoint", async () => {
    const resp = { providers: [], models: [], agents: [] };
    mockApiRequest.mockResolvedValue(resp as never);
    const result = await fetchLlmUsageFilterOptions();
    expect(mockApiRequest).toHaveBeenCalledWith("get", "/analytics/llm-usage/filter-options");
    expect(result).toBe(resp);
  });
});
