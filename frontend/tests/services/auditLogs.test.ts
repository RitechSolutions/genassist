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
import { fetchAuditLogs, fetchAuditLogDetails, fetchUsers } from "@/services/auditLogs";

const mockApiRequest = vi.mocked(apiRequest);
beforeEach(() => vi.clearAllMocks());

describe("fetchAuditLogs", () => {
  it("appends every truthy filter plus limit/offset and returns the list", async () => {
    const logs = [{ id: "1" }];
    mockApiRequest.mockResolvedValue(logs as never);

    const result = await fetchAuditLogs(
      "2024-01-01",
      "2024-02-01",
      "UPDATE",
      "users",
      "alice",
      50,
      10,
    );

    expect(mockApiRequest).toHaveBeenCalledWith(
      "GET",
      "/audit-logs/search?date_from=2024-01-01&date_to=2024-02-01&action=UPDATE" +
        "&table_name=users&user=alice&limit=50&offset=10",
    );
    expect(result).toEqual(logs);
  });

  it("omits empty filters, keeping only limit and offset", async () => {
    mockApiRequest.mockResolvedValue([] as never);

    await fetchAuditLogs("", "", "", "", "", 25, 0);

    expect(mockApiRequest).toHaveBeenCalledWith(
      "GET",
      "/audit-logs/search?limit=25&offset=0",
    );
  });

  it("returns an empty array when the response is null", async () => {
    mockApiRequest.mockResolvedValue(null as never);

    await expect(fetchAuditLogs("", "", "", "", "", 25, 0)).resolves.toEqual([]);
  });
});

describe("fetchAuditLogDetails", () => {
  it("GETs the audit log and returns it when json_changes exists", async () => {
    const log = { id: "1", json_changes: { a: 1 } };
    mockApiRequest.mockResolvedValue(log as never);

    const result = await fetchAuditLogDetails("1");

    expect(mockApiRequest).toHaveBeenCalledWith("GET", "/audit-logs/1");
    expect(result).toEqual(log);
  });

  it("throws when no audit log is returned", async () => {
    mockApiRequest.mockResolvedValue(null as never);

    await expect(fetchAuditLogDetails("123")).rejects.toThrow(
      "No audit log found with ID: 123",
    );
  });

  it("throws when json_changes is missing", async () => {
    mockApiRequest.mockResolvedValue({ id: "1" } as never);

    await expect(fetchAuditLogDetails("1")).rejects.toThrow(
      "No json_changes found in the audit log.",
    );
  });
});

describe("fetchUsers", () => {
  it("GETs user/ and returns the list", async () => {
    const users = [{ id: "u1" }];
    mockApiRequest.mockResolvedValue(users as never);

    const result = await fetchUsers();

    expect(mockApiRequest).toHaveBeenCalledWith("GET", "user/");
    expect(result).toEqual(users);
  });

  it("returns an empty array when the response is null", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    await expect(fetchUsers()).resolves.toEqual([]);
  });
});
