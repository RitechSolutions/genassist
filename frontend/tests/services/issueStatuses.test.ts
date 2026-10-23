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
  createIssueStatus,
  fetchIssueStatuses,
  reorderIssueStatuses,
  updateIssueStatus,
} from "@/services/issueStatuses";

const mockApiRequest = vi.mocked(apiRequest);
beforeEach(() => vi.clearAllMocks());

describe("fetchIssueStatuses", () => {
  it("GETs issue-statuses and returns the list", async () => {
    const statuses = [{ key: "open" }];
    mockApiRequest.mockResolvedValue(statuses as never);
    expect(await fetchIssueStatuses()).toBe(statuses);
    expect(mockApiRequest).toHaveBeenCalledWith("GET", "issue-statuses");
  });

  it("returns [] when the response is null", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    expect(await fetchIssueStatuses()).toEqual([]);
  });
});

describe("issue status writes", () => {
  it("POSTs a new status", async () => {
    const body = { key: "blocked", label: "Blocked", category: "in_progress" as const, color: "red" };
    mockApiRequest.mockResolvedValue({ id: "s1", ...body } as never);
    await createIssueStatus(body);
    expect(mockApiRequest).toHaveBeenCalledWith("POST", "issue-statuses", body);
  });

  it("PATCHes only the given fields", async () => {
    mockApiRequest.mockResolvedValue({ id: "s1" } as never);
    await updateIssueStatus("s1", { is_active: 0 });
    expect(mockApiRequest).toHaveBeenCalledWith("PATCH", "issue-statuses/s1", { is_active: 0 });
  });

  it("PUTs the full key order", async () => {
    mockApiRequest.mockResolvedValue([] as never);
    await reorderIssueStatuses(["open", "blocked"]);
    expect(mockApiRequest).toHaveBeenCalledWith("PUT", "issue-statuses/order", {
      keys: ["open", "blocked"],
    });
  });

  it("throws on a null (403) response instead of looking saved", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    await expect(
      createIssueStatus({ key: "x1", label: "X", category: "todo", color: "red" }),
    ).rejects.toThrow();
    await expect(updateIssueStatus("s1", { label: "X" })).rejects.toThrow();
    await expect(reorderIssueStatuses(["open"])).rejects.toThrow();
  });
});
