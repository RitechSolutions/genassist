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
  getAllPermissions,
  getPermissionsByRoleId,
  saveRolePermissions,
} from "@/services/permission";

const mockApiRequest = vi.mocked(apiRequest);
beforeEach(() => vi.clearAllMocks());

describe("getAllPermissions", () => {
  it("requests the permissions list and returns it", async () => {
    const permissions = [{ id: "p1" }];
    mockApiRequest.mockResolvedValue(permissions as never);

    const result = await getAllPermissions();

    expect(mockApiRequest).toHaveBeenCalledWith("GET", "/permissions");
    expect(result).toBe(permissions);
  });

  // apiRequest resolves with null on 403 rather than throwing.
  it("throws rather than returning an empty list when the response is null", async () => {
    mockApiRequest.mockResolvedValue(null as never);

    await expect(getAllPermissions()).rejects.toThrow(/permission/i);
  });

  it("propagates errors", async () => {
    mockApiRequest.mockRejectedValue(new Error("boom"));

    await expect(getAllPermissions()).rejects.toThrow("boom");
  });
});

describe("getPermissionsByRoleId", () => {
  it("reads the role's permission ids from the scoped endpoint", async () => {
    mockApiRequest.mockResolvedValue(["p1", "p2"] as never);

    const result = await getPermissionsByRoleId("r1");

    expect(mockApiRequest).toHaveBeenCalledWith("GET", "/roles/r1/permissions");
    expect(result).toEqual(["p1", "p2"]);
  });

  // Returning [] here would look identical to "this role has no permissions",
  // and saving that empty set would wipe the role.
  it("throws instead of reporting an empty permission set when denied", async () => {
    mockApiRequest.mockResolvedValue(null as never);

    await expect(getPermissionsByRoleId("r1")).rejects.toThrow(/permission/i);
  });

  it("propagates errors", async () => {
    mockApiRequest.mockRejectedValue(new Error("boom"));

    await expect(getPermissionsByRoleId("r1")).rejects.toThrow("boom");
  });
});

describe("saveRolePermissions", () => {
  it("sends the full selection to the bulk endpoint in one request", async () => {
    mockApiRequest.mockResolvedValue({ role_id: "r1" } as never);

    await saveRolePermissions("r1", ["p2", "p3"]);

    expect(mockApiRequest).toHaveBeenCalledTimes(1);
    expect(mockApiRequest).toHaveBeenCalledWith(
      "PUT",
      "/roles/r1/permissions",
      { permission_ids: ["p2", "p3"] },
      {},
      { rethrowForbidden: true }
    );
  });

  it("sends an empty list when every permission is cleared", async () => {
    mockApiRequest.mockResolvedValue({ role_id: "r1" } as never);

    await saveRolePermissions("r1", []);

    expect(mockApiRequest).toHaveBeenCalledWith(
      "PUT",
      "/roles/r1/permissions",
      { permission_ids: [] },
      {},
      { rethrowForbidden: true }
    );
  });

  // A 403 here can mean "reserved for the admin role", which the admin can act
  // on only if the server's message reaches them intact.
  it("lets a forbidden response surface its own message", async () => {
    const forbidden = Object.assign(new Error("Request failed"), {
      response: {
        status: 403,
        data: { error: "This permission can only be assigned to the admin role." },
      },
    });
    mockApiRequest.mockRejectedValue(forbidden);

    await expect(saveRolePermissions("r1", ["p2"])).rejects.toBe(forbidden);
  });

  // The dialog reports success off this resolving, so a failed write must reject.
  it("throws when the write fails", async () => {
    mockApiRequest.mockRejectedValue(new Error("write failed"));

    await expect(saveRolePermissions("r1", ["p2"])).rejects.toThrow("write failed");
  });

  it("throws when the write is rejected with a null response", async () => {
    mockApiRequest.mockResolvedValue(null as never);

    await expect(saveRolePermissions("r1", ["p2"])).rejects.toThrow(/permission/i);
  });
});
