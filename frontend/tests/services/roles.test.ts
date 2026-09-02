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
  getAllRoles,
  getRole,
  createRole,
  deleteRole,
  updateRole,
} from "@/services/roles";

const mockApiRequest = vi.mocked(apiRequest);
beforeEach(() => vi.clearAllMocks());

describe("getAllRoles", () => {
  it("requests the roles list and returns it", async () => {
    const roles = [{ id: "1" }];
    mockApiRequest.mockResolvedValue(roles as never);

    const result = await getAllRoles();

    expect(mockApiRequest).toHaveBeenCalledWith("GET", "roles/");
    expect(result).toBe(roles);
  });

  it("falls back to an empty array when the response is null", async () => {
    mockApiRequest.mockResolvedValue(null as never);

    await expect(getAllRoles()).resolves.toEqual([]);
  });

  it("propagates errors", async () => {
    mockApiRequest.mockRejectedValue(new Error("boom"));

    await expect(getAllRoles()).rejects.toThrow("boom");
  });
});

describe("getRole", () => {
  it("requests a single role by id and returns it", async () => {
    const role = { id: "7" };
    mockApiRequest.mockResolvedValue(role as never);

    const result = await getRole("7");

    expect(mockApiRequest).toHaveBeenCalledWith("GET", "roles/7");
    expect(result).toBe(role);
  });

  it("returns null when the response is null", async () => {
    mockApiRequest.mockResolvedValue(null as never);

    await expect(getRole("7")).resolves.toBeNull();
  });

  it("propagates errors", async () => {
    mockApiRequest.mockRejectedValue(new Error("boom"));

    await expect(getRole("7")).rejects.toThrow("boom");
  });
});

describe("createRole", () => {
  it("posts the role data and returns the created role", async () => {
    const created = { id: "new" };
    mockApiRequest.mockResolvedValue(created as never);

    const result = await createRole({ name: "admin" });

    expect(mockApiRequest).toHaveBeenCalledWith("POST", "roles", { name: "admin" });
    expect(result).toBe(created);
  });

  it("throws when the response is null", async () => {
    mockApiRequest.mockResolvedValue(null as never);

    await expect(createRole({ name: "x" })).rejects.toThrow("Failed to create role");
  });

  it("propagates errors", async () => {
    mockApiRequest.mockRejectedValue(new Error("boom"));

    await expect(createRole({ name: "x" })).rejects.toThrow("boom");
  });
});

describe("deleteRole", () => {
  it("deletes the role by id and resolves to undefined", async () => {
    mockApiRequest.mockResolvedValue(undefined as never);

    const result = await deleteRole("7");

    expect(mockApiRequest).toHaveBeenCalledWith("DELETE", "roles/7");
    expect(result).toBeUndefined();
  });

  it("propagates errors", async () => {
    mockApiRequest.mockRejectedValue(new Error("boom"));

    await expect(deleteRole("7")).rejects.toThrow("boom");
  });
});

describe("updateRole", () => {
  it("patches the role data and returns the updated role", async () => {
    const updated = { id: "7", name: "admin2" };
    mockApiRequest.mockResolvedValue(updated as never);

    const result = await updateRole("7", { name: "admin2" });

    expect(mockApiRequest).toHaveBeenCalledWith("PATCH", "roles/7", { name: "admin2" });
    expect(result).toBe(updated);
  });

  it("throws when the response is null", async () => {
    mockApiRequest.mockResolvedValue(null as never);

    await expect(updateRole("7", {})).rejects.toThrow("Failed to update role");
  });

  it("propagates errors", async () => {
    mockApiRequest.mockRejectedValue(new Error("boom"));

    await expect(updateRole("7", {})).rejects.toThrow("boom");
  });
});
