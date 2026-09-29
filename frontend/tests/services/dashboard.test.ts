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
  fetchDashboard,
  fetchDashboardSummary,
  fetchDashboardConversations,
  fetchDashboardAgents,
  fetchDashboardIntegrations,
  fetchDashboardNotificationsPage,
  fetchDashboardNotifications,
  markNotificationsRead,
  getFilterDays,
} from "@/services/dashboard";

const mockApiRequest = vi.mocked(apiRequest);
// Several functions log via console.error in their catch blocks; keep test output clean.
vi.spyOn(console, "error").mockImplementation(() => {});
beforeEach(() => vi.clearAllMocks());

describe("fetchDashboard", () => {
  it("calls apiRequest with default query params and returns the payload", async () => {
    const payload = { foo: "bar" };
    mockApiRequest.mockResolvedValue(payload as never);
    const result = await fetchDashboard();
    expect(mockApiRequest).toHaveBeenCalledWith(
      "get",
      "/dashboard?days=30&conversations_page=1&conversations_page_size=3"
    );
    expect(result).toBe(payload);
  });

  it("threads custom arguments into the query string", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    await fetchDashboard(7, 2, 5);
    expect(mockApiRequest).toHaveBeenCalledWith(
      "get",
      "/dashboard?days=7&conversations_page=2&conversations_page_size=5"
    );
  });

  it("returns null when apiRequest rejects", async () => {
    mockApiRequest.mockRejectedValue(new Error("boom"));
    expect(await fetchDashboard()).toBeNull();
  });
});

describe("fetchDashboardSummary", () => {
  it("defaults to a days range", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    await fetchDashboardSummary();
    expect(mockApiRequest).toHaveBeenCalledWith("get", "/dashboard/summary?days=30");
  });

  it("supports an all_time range", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    await fetchDashboardSummary({ all_time: true });
    expect(mockApiRequest).toHaveBeenCalledWith("get", "/dashboard/summary?all_time=true");
  });

  it("supports a from/to datetime range", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    await fetchDashboardSummary({
      from_datetime: "2025-01-01T00:00:00Z",
      to_datetime: "2025-02-01T00:00:00Z",
    });
    expect(mockApiRequest).toHaveBeenCalledWith(
      "get",
      "/dashboard/summary?from_datetime=2025-01-01T00%3A00%3A00Z&to_datetime=2025-02-01T00%3A00%3A00Z"
    );
  });

  it("returns the raw apiRequest value", async () => {
    const stats = { total: 1 };
    mockApiRequest.mockResolvedValue(stats as never);
    expect(await fetchDashboardSummary()).toBe(stats);
  });
});

describe("fetchDashboardConversations", () => {
  it("uses default pagination params", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    await fetchDashboardConversations();
    expect(mockApiRequest).toHaveBeenCalledWith(
      "get",
      "/dashboard/conversations?days=30&page=1&page_size=10"
    );
  });

  it("threads custom pagination params", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    await fetchDashboardConversations(7, 3, 25);
    expect(mockApiRequest).toHaveBeenCalledWith(
      "get",
      "/dashboard/conversations?days=7&page=3&page_size=25"
    );
  });

  it("returns null on rejection", async () => {
    mockApiRequest.mockRejectedValue(new Error("boom"));
    expect(await fetchDashboardConversations()).toBeNull();
  });
});

describe("fetchDashboardAgents", () => {
  it("uses default days", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    await fetchDashboardAgents();
    expect(mockApiRequest).toHaveBeenCalledWith("get", "/dashboard/agents?days=30");
  });

  it("returns null on rejection", async () => {
    mockApiRequest.mockRejectedValue(new Error("boom"));
    expect(await fetchDashboardAgents(90)).toBeNull();
  });
});

describe("fetchDashboardIntegrations", () => {
  it("calls the integrations endpoint", async () => {
    const data = { integrations: [] };
    mockApiRequest.mockResolvedValue(data as never);
    const result = await fetchDashboardIntegrations();
    expect(mockApiRequest).toHaveBeenCalledWith("get", "/dashboard/integrations");
    expect(result).toBe(data);
  });

  it("returns null on rejection", async () => {
    mockApiRequest.mockRejectedValue(new Error("boom"));
    expect(await fetchDashboardIntegrations()).toBeNull();
  });
});

describe("fetchDashboardNotificationsPage", () => {
  it("builds the query string and maps raw items", async () => {
    mockApiRequest.mockResolvedValue({
      items: [
        {
          id: "n1",
          notification_id: "nid1",
          type_key: "conversation_started",
          group_id: "grp1",
          title: "Title",
          description: "Desc",
          timestamp: "2025-01-01T00:00:00Z",
          type: "info",
          is_read: true,
          action_url: "/go",
        },
      ],
      has_more: true,
    } as never);

    const result = await fetchDashboardNotificationsPage(
      10,
      0,
      true,
      false,
      true,
      false,
      "all",
      "info"
    );

    expect(mockApiRequest).toHaveBeenCalledWith(
      "get",
      "/dashboard/notifications?limit=10&skip=0&notification_type=all&include_conversation_started=true&include_conversation_hostility=false&include_conversation_finalized_hostility=true&include_workflow_failed=false&notification_level=info"
    );
    expect(result).toEqual({
      items: [
        {
          id: "n1",
          notificationId: "nid1",
          typeKey: "conversation_started",
          groupId: "grp1",
          title: "Title",
          description: "Desc",
          timestamp: "2025-01-01T00:00:00Z",
          type: "info",
          read: true,
          actionUrl: "/go",
        },
      ],
      hasMore: true,
    });
  });

  it("coerces missing is_read/has_more to false", async () => {
    mockApiRequest.mockResolvedValue({
      items: [
        {
          id: "n2",
          title: "T",
          description: "D",
          timestamp: "t",
          type: "info",
          action_url: "/x",
        },
      ],
    } as never);
    const result = await fetchDashboardNotificationsPage(5, 0, true, true, true, true);
    expect(result?.items[0].read).toBe(false);
    expect(result?.hasMore).toBe(false);
  });

  it("returns null when apiRequest resolves null", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    expect(await fetchDashboardNotificationsPage(5, 0, true, true, true, true)).toBeNull();
  });

  it("returns null on rejection", async () => {
    mockApiRequest.mockRejectedValue(new Error("boom"));
    expect(await fetchDashboardNotificationsPage(5, 0, true, true, true, true)).toBeNull();
  });
});

describe("fetchDashboardNotifications", () => {
  it("delegates with defaults and returns items", async () => {
    mockApiRequest.mockResolvedValue({
      items: [
        {
          id: "n1",
          title: "T",
          description: "D",
          timestamp: "t",
          type: "info",
          is_read: false,
          action_url: "/x",
        },
      ],
      has_more: false,
    } as never);

    const result = await fetchDashboardNotifications();
    expect(mockApiRequest).toHaveBeenCalledWith(
      "get",
      "/dashboard/notifications?limit=50&skip=0&notification_type=all&include_conversation_started=true&include_conversation_hostility=true&include_conversation_finalized_hostility=true&include_workflow_failed=true&notification_level=all"
    );
    expect(result).toHaveLength(1);
    expect(result?.[0].id).toBe("n1");
  });

  it("returns null when the underlying page is null", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    expect(await fetchDashboardNotifications()).toBeNull();
  });
});

describe("markNotificationsRead", () => {
  it("patches the read state and returns true", async () => {
    mockApiRequest.mockResolvedValue({ updated_count: 2 } as never);
    const result = await markNotificationsRead(["a", "b"]);
    expect(mockApiRequest).toHaveBeenCalledWith("patch", "/notifications/state/read", {
      notification_ids: ["a", "b"],
      is_read: true,
    });
    expect(result).toBe(true);
  });

  it("passes an explicit is_read flag", async () => {
    mockApiRequest.mockResolvedValue({ updated_count: 0 } as never);
    await markNotificationsRead(["a"], false);
    expect(mockApiRequest).toHaveBeenCalledWith("patch", "/notifications/state/read", {
      notification_ids: ["a"],
      is_read: false,
    });
  });

  it("returns false on rejection", async () => {
    mockApiRequest.mockRejectedValue(new Error("boom"));
    expect(await markNotificationsRead(["a"])).toBe(false);
  });
});

describe("getFilterDays", () => {
  it("maps each known filter to its day count", () => {
    expect(getFilterDays("today")).toBe(1);
    expect(getFilterDays("7days")).toBe(7);
    expect(getFilterDays("30days")).toBe(30);
    expect(getFilterDays("6months")).toBe(180);
    expect(getFilterDays("12months")).toBe(365);
  });

  it("defaults unknown values to 30", () => {
    expect(getFilterDays("nope")).toBe(30);
  });
});
