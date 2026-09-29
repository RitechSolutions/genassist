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
  fetchGroupAgents,
  fetchAgentDailyStats,
  fetchAgentStatsSummary,
  triggerAnalyticsBackfill,
  fetchAgentStatsSummaryWithComparison,
  fetchNodeDailyStats,
  fetchAgentNodeBreakdown,
  fetchCustomAttributeKeys,
  fetchCustomAttributeBreakdown,
} from "@/services/analyticsReports";

const mockApiRequest = vi.mocked(apiRequest);
vi.spyOn(console, "error").mockImplementation(() => {});
beforeEach(() => vi.clearAllMocks());

describe("fetchGroupAgents", () => {
  it("returns the array from apiRequest", async () => {
    const agents = [{ id: "a1" }];
    mockApiRequest.mockResolvedValue(agents as never);
    const result = await fetchGroupAgents("g1");
    expect(mockApiRequest).toHaveBeenCalledWith("get", "/analytics/groups/g1/agents");
    expect(result).toBe(agents);
  });

  it("throws when apiRequest does not return an array (null)", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    await expect(fetchGroupAgents("g1")).rejects.toThrow("Failed to fetch group agents");
  });

  it("throws when apiRequest returns a non-array object", async () => {
    mockApiRequest.mockResolvedValue({ nope: true } as never);
    await expect(fetchGroupAgents("g1")).rejects.toThrow("Failed to fetch group agents");
  });
});

describe("fetchAgentDailyStats", () => {
  it("omits the query string when no params are given", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    await fetchAgentDailyStats();
    expect(mockApiRequest).toHaveBeenCalledWith("get", "/analytics/agents");
  });

  it("builds the query string from the provided params", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    await fetchAgentDailyStats({
      agent_id: "a1",
      group_id: "g1",
      from_date: "2025-01-01",
      to_date: "2025-02-01",
    });
    expect(mockApiRequest).toHaveBeenCalledWith(
      "get",
      "/analytics/agents?agent_id=a1&group_id=g1&from_date=2025-01-01&to_date=2025-02-01"
    );
  });

  it("returns null on rejection", async () => {
    mockApiRequest.mockRejectedValue(new Error("boom"));
    expect(await fetchAgentDailyStats()).toBeNull();
  });
});

describe("fetchAgentStatsSummary", () => {
  it("builds the summary query string", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    await fetchAgentStatsSummary({ agent_id: "a1" });
    expect(mockApiRequest).toHaveBeenCalledWith("get", "/analytics/agents/summary?agent_id=a1");
  });

  it("returns null on rejection", async () => {
    mockApiRequest.mockRejectedValue(new Error("boom"));
    expect(await fetchAgentStatsSummary()).toBeNull();
  });
});

describe("triggerAnalyticsBackfill", () => {
  it("posts with an empty query string when no params", async () => {
    const resp = { status: "queued", task_id: "t1", from_date: null, to_date: null };
    mockApiRequest.mockResolvedValue(resp as never);
    const result = await triggerAnalyticsBackfill();
    expect(mockApiRequest).toHaveBeenCalledWith("post", "/analytics/backfill");
    expect(result).toBe(resp);
  });

  it("posts with a query string built from params", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    await triggerAnalyticsBackfill({ from_date: "2025-01-01", to_date: "2025-02-01" });
    expect(mockApiRequest).toHaveBeenCalledWith(
      "post",
      "/analytics/backfill?from_date=2025-01-01&to_date=2025-02-01"
    );
  });

  it("propagates rejections (errors are not swallowed)", async () => {
    mockApiRequest.mockRejectedValue(new Error("boom"));
    await expect(triggerAnalyticsBackfill()).rejects.toThrow("boom");
  });
});

describe("fetchAgentStatsSummaryWithComparison", () => {
  it("always appends compare=true", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    await fetchAgentStatsSummaryWithComparison({ agent_id: "a1" });
    expect(mockApiRequest).toHaveBeenCalledWith(
      "get",
      "/analytics/agents/summary?agent_id=a1&compare=true"
    );
  });

  it("appends compare=true even without other params", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    await fetchAgentStatsSummaryWithComparison();
    expect(mockApiRequest).toHaveBeenCalledWith("get", "/analytics/agents/summary?compare=true");
  });

  it("returns null on rejection", async () => {
    mockApiRequest.mockRejectedValue(new Error("boom"));
    expect(await fetchAgentStatsSummaryWithComparison()).toBeNull();
  });
});

describe("fetchNodeDailyStats", () => {
  it("builds the nodes query string", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    await fetchNodeDailyStats({ agent_id: "a1", node_type: "llm" });
    expect(mockApiRequest).toHaveBeenCalledWith("get", "/analytics/nodes?agent_id=a1&node_type=llm");
  });

  it("returns null on rejection", async () => {
    mockApiRequest.mockRejectedValue(new Error("boom"));
    expect(await fetchNodeDailyStats()).toBeNull();
  });
});

describe("fetchAgentNodeBreakdown", () => {
  it("embeds the agent id and appends date params", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    await fetchAgentNodeBreakdown("agent-1", { from_date: "2025-01-01" });
    expect(mockApiRequest).toHaveBeenCalledWith(
      "get",
      "/analytics/agents/agent-1/nodes/breakdown?from_date=2025-01-01"
    );
  });

  it("omits the query string when no params", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    await fetchAgentNodeBreakdown("agent-1");
    expect(mockApiRequest).toHaveBeenCalledWith(
      "get",
      "/analytics/agents/agent-1/nodes/breakdown"
    );
  });

  it("returns null on rejection", async () => {
    mockApiRequest.mockRejectedValue(new Error("boom"));
    expect(await fetchAgentNodeBreakdown("agent-1")).toBeNull();
  });
});

describe("fetchCustomAttributeKeys", () => {
  it("returns the array from apiRequest", async () => {
    mockApiRequest.mockResolvedValue(["dept", "tier"] as never);
    const result = await fetchCustomAttributeKeys({ agent_id: "a1" });
    expect(mockApiRequest).toHaveBeenCalledWith(
      "get",
      "/analytics/custom-attributes/keys?agent_id=a1"
    );
    expect(result).toEqual(["dept", "tier"]);
  });

  it("falls back to [] when apiRequest resolves null", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    expect(await fetchCustomAttributeKeys()).toEqual([]);
  });

  it("returns [] on rejection", async () => {
    mockApiRequest.mockRejectedValue(new Error("boom"));
    expect(await fetchCustomAttributeKeys()).toEqual([]);
  });
});

describe("fetchCustomAttributeBreakdown", () => {
  it("includes the key first and other params after", async () => {
    const items = [{ value: "x", conversation_count: 1 }];
    mockApiRequest.mockResolvedValue(items as never);
    const result = await fetchCustomAttributeBreakdown("dept", { agent_id: "a1" });
    expect(mockApiRequest).toHaveBeenCalledWith(
      "get",
      "/analytics/custom-attributes/breakdown?key=dept&agent_id=a1"
    );
    expect(result).toBe(items);
  });

  it("falls back to [] when apiRequest resolves null", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    expect(await fetchCustomAttributeBreakdown("dept")).toEqual([]);
  });

  it("returns [] on rejection", async () => {
    mockApiRequest.mockRejectedValue(new Error("boom"));
    expect(await fetchCustomAttributeBreakdown("dept")).toEqual([]);
  });
});
