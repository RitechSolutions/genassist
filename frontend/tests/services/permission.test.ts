import { describe, it, expect, vi, beforeEach } from "vitest";
import type { Method } from "axios";

vi.mock("@/config/api", () => ({
  apiRequest: vi.fn(),
  getApiUrl: vi.fn(async () => "http://localhost/api/"),
  getApiUrlString: "http://localhost/api/",
  formatUploadOrNetworkError: (e: unknown) => (e instanceof Error ? e.message : String(e)),
  API_DEFAULT_TIMEOUT_MS: 1000,
  API_UPLOAD_TIMEOUT_MS: 1000,
  api: { get: vi.fn(), post: vi.fn(), put: vi.fn(), patch: vi.fn(), delete: vi.fn(), request: vi.fn() },
}));

const { toastError } = vi.hoisted(() => ({ toastError: vi.fn() }));
vi.mock("react-hot-toast", () => ({
  default: { error: toastError, success: vi.fn() },
}));

import { apiRequest } from "@/config/api";
import {
  getAllPermissions,
  getRolePermissions,
  getPermissionsByRoleId,
  getRolePermissionLinksByRoleId,
  saveRolePermissions,
} from "@/services/permission";

const mockApiRequest = vi.mocked(apiRequest);
beforeEach(() => vi.clearAllMocks());

describe("getAllPermissions", () => {
  it("requests the permissions list and returns it", async () => {
    const permissions = [{ id: "p1" }];
    mockApiRequest.mockResolvedValue(permissions as never);

    const result = await getAllPermissions("create");

    expect(mockApiRequest).toHaveBeenCalledWith("GET", "/permissions");
    expect(result).toBe(permissions);
  });

  it("falls back to an empty array when the response is null", async () => {
    mockApiRequest.mockResolvedValue(null as never);

    await expect(getAllPermissions("edit")).resolves.toEqual([]);
  });

  it("propagates errors", async () => {
    mockApiRequest.mockRejectedValue(new Error("boom"));

    await expect(getAllPermissions("create")).rejects.toThrow("boom");
  });
});

describe("getRolePermissions", () => {
  it("requests the role and returns its permissions", async () => {
    mockApiRequest.mockResolvedValue({ permissions: ["a", "b"] } as never);

    const result = await getRolePermissions("r1");

    expect(mockApiRequest).toHaveBeenCalledWith("GET", "/roles/r1");
    expect(result).toEqual(["a", "b"]);
  });

  it("returns an empty array when the role has no permissions field", async () => {
    mockApiRequest.mockResolvedValue({} as never);

    await expect(getRolePermissions("r1")).resolves.toEqual([]);
  });

  it("returns an empty array on error", async () => {
    mockApiRequest.mockRejectedValue(new Error("boom"));

    await expect(getRolePermissions("r1")).resolves.toEqual([]);
  });
});

describe("getPermissionsByRoleId", () => {
  it("requests the role-permission links and returns the matching permission ids", async () => {
    mockApiRequest.mockResolvedValue([
      { role_id: "r1", permission_id: "p1" },
      { role_id: "r1", permission_id: "p2" },
      { role_id: "r2", permission_id: "p3" },
    ] as never);

    const result = await getPermissionsByRoleId("r1");

    expect(mockApiRequest).toHaveBeenCalledWith("GET", "/role-permissions");
    expect(result).toEqual(["p1", "p2"]);
  });

  it("returns an empty array on error", async () => {
    mockApiRequest.mockRejectedValue(new Error("boom"));

    await expect(getPermissionsByRoleId("r1")).resolves.toEqual([]);
  });
});

describe("getRolePermissionLinksByRoleId", () => {
  it("requests the role-permission links and returns the matching link objects", async () => {
    const links = [
      { id: "l1", role_id: "r1", permission_id: "p1" },
      { id: "l2", role_id: "r2", permission_id: "p2" },
    ];
    mockApiRequest.mockResolvedValue(links as never);

    const result = await getRolePermissionLinksByRoleId("r1");

    expect(mockApiRequest).toHaveBeenCalledWith("GET", "/role-permissions");
    expect(result).toEqual([{ id: "l1", role_id: "r1", permission_id: "p1" }]);
  });

  it("returns an empty array on error", async () => {
    mockApiRequest.mockRejectedValue(new Error("boom"));

    await expect(getRolePermissionLinksByRoleId("r1")).resolves.toEqual([]);
  });
});

describe("saveRolePermissions", () => {
  const links = [
    { id: "l1", role_id: "r1", permission_id: "p1" },
    { id: "l2", role_id: "r1", permission_id: "p2" },
    { id: "l3", role_id: "r2", permission_id: "p3" },
  ];

  it("adds newly selected permissions and deletes deselected links", async () => {
    mockApiRequest.mockResolvedValue(links as never);

    // existing for r1 = [p1, p2]; selecting [p2, p3] => add p3, delete link l1 (p1)
    await saveRolePermissions("r1", ["p2", "p3"]);

    expect(mockApiRequest).toHaveBeenCalledWith("POST", "/role-permissions", {
      role_id: "r1",
      permission_id: "p3",
      is_active: true,
    });
    expect(mockApiRequest).toHaveBeenCalledWith("DELETE", "/role-permissions/l1");
    expect(mockApiRequest).not.toHaveBeenCalledWith("DELETE", "/role-permissions/l2");
    expect(toastError).not.toHaveBeenCalled();
  });

  it("shows a toast and does not throw when a write fails", async () => {
    mockApiRequest.mockImplementation((method: Method) => {
      if (method === "GET") return Promise.resolve(links as never);
      return Promise.reject(new Error("write failed"));
    });

    await expect(saveRolePermissions("r1", ["p2", "p3"])).resolves.toBeUndefined();
    expect(toastError).toHaveBeenCalledWith("Failed to update role permissions.");
  });
});
