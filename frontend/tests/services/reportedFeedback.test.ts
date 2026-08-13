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
import { fetchReportedFeedback, updateFeedbackStatus } from "@/services/reportedFeedback";

const mockApiRequest = vi.mocked(apiRequest);
beforeEach(() => vi.clearAllMocks());

const EMPTY_RESULT = {
  items: [],
  total: 0,
  page: 1,
  page_size: 20,
  total_pages: 0,
};

describe("fetchReportedFeedback", () => {
  it("uses only limit=20 with default params (skip omitted)", async () => {
    const resp = { items: [], total: 0, page: 1, page_size: 20, total_pages: 0 };
    mockApiRequest.mockResolvedValue(resp as never);
    const result = await fetchReportedFeedback();
    expect(mockApiRequest).toHaveBeenCalledWith("GET", "conversations/issues?limit=20");
    expect(result).toBe(resp);
  });

  it("appends all provided params in order", async () => {
    mockApiRequest.mockResolvedValue(EMPTY_RESULT as never);
    await fetchReportedFeedback({
      skip: 10,
      limit: 50,
      status: "open",
      from_date: "2025-01-01",
      to_date: "2025-02-01",
      workflow_id: "w1",
    });
    expect(mockApiRequest).toHaveBeenCalledWith(
      "GET",
      "conversations/issues?skip=10&limit=50&status=open&from_date=2025-01-01&to_date=2025-02-01&workflow_id=w1"
    );
  });

  it("omits the status param when status is 'all'", async () => {
    mockApiRequest.mockResolvedValue(EMPTY_RESULT as never);
    await fetchReportedFeedback({ status: "all" });
    expect(mockApiRequest).toHaveBeenCalledWith("GET", "conversations/issues?limit=20");
  });

  it("clamps limit to the backend max of 100", async () => {
    mockApiRequest.mockResolvedValue(EMPTY_RESULT as never);
    await fetchReportedFeedback({ limit: 500 });
    expect(mockApiRequest).toHaveBeenCalledWith("GET", "conversations/issues?limit=100");
  });

  it("falls back to limit=20 when limit is not positive", async () => {
    mockApiRequest.mockResolvedValue(EMPTY_RESULT as never);
    await fetchReportedFeedback({ limit: 0 });
    expect(mockApiRequest).toHaveBeenCalledWith("GET", "conversations/issues?limit=20");
  });

  it("returns the EMPTY_RESULT fallback when apiRequest resolves null", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    expect(await fetchReportedFeedback()).toEqual(EMPTY_RESULT);
  });
});

describe("updateFeedbackStatus", () => {
  it("patches the status endpoint with the status body", async () => {
    mockApiRequest.mockResolvedValue(undefined as never);
    await updateFeedbackStatus("f1", "resolved");
    expect(mockApiRequest).toHaveBeenCalledWith("PATCH", "conversations/issues/f1/status", {
      status: "resolved",
    });
  });
});
