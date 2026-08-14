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
  fetchMetrics,
  fetchMetricsWithComparison,
  fetchMetricsDaily,
  fetchTopicsReport,
} from "@/services/metrics";

const mockApiRequest = vi.mocked(apiRequest);
beforeEach(() => vi.clearAllMocks());

describe("fetchMetrics", () => {
  it("hits the metrics endpoint with no query when no params", async () => {
    const data = { Efficiency: "90%" };
    mockApiRequest.mockResolvedValue(data as never);
    const result = await fetchMetrics();
    expect(mockApiRequest).toHaveBeenCalledWith("get", "/analytics/metrics");
    expect(result).toBe(data);
  });

  it("builds the query string from params", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    await fetchMetrics({
      from_date: "2025-01-01",
      to_date: "2025-02-01",
      agent_id: "a1",
      group_id: "g1",
    });
    expect(mockApiRequest).toHaveBeenCalledWith(
      "get",
      "/analytics/metrics?from_date=2025-01-01&to_date=2025-02-01&agent_id=a1&group_id=g1"
    );
  });

  it("propagates rejections", async () => {
    mockApiRequest.mockRejectedValue(new Error("boom"));
    await expect(fetchMetrics()).rejects.toThrow("boom");
  });
});

describe("fetchMetricsWithComparison", () => {
  it("appends compare=true with other params", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    await fetchMetricsWithComparison({ agent_id: "a1" });
    expect(mockApiRequest).toHaveBeenCalledWith(
      "get",
      "/analytics/metrics?agent_id=a1&compare=true"
    );
  });

  it("appends compare=true even without params", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    await fetchMetricsWithComparison();
    expect(mockApiRequest).toHaveBeenCalledWith("get", "/analytics/metrics?compare=true");
  });
});

describe("fetchMetricsDaily", () => {
  it("returns the items array from the response", async () => {
    const items = [{ date: "2025-01-01", satisfaction: 1, quality_of_service: 2, resolution_rate: 3, efficiency: 4 }];
    mockApiRequest.mockResolvedValue({ items } as never);
    const result = await fetchMetricsDaily();
    expect(mockApiRequest).toHaveBeenCalledWith("get", "/analytics/metrics/daily");
    expect(result).toBe(items);
  });

  it("returns [] when response is null", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    expect(await fetchMetricsDaily()).toEqual([]);
  });

  it("returns [] when response has no items", async () => {
    mockApiRequest.mockResolvedValue({} as never);
    expect(await fetchMetricsDaily()).toEqual([]);
  });

  it("builds the daily query string from params", async () => {
    mockApiRequest.mockResolvedValue({ items: [] } as never);
    await fetchMetricsDaily({ agent_id: "a1" });
    expect(mockApiRequest).toHaveBeenCalledWith("get", "/analytics/metrics/daily?agent_id=a1");
  });
});

describe("fetchTopicsReport", () => {
  it("hits the topics-report endpoint and returns the payload", async () => {
    const report = { topics: [] };
    mockApiRequest.mockResolvedValue(report as never);
    const result = await fetchTopicsReport();
    expect(mockApiRequest).toHaveBeenCalledWith("get", "/topics-report");
    expect(result).toBe(report);
  });
});
