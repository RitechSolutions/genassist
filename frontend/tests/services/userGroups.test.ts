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
  getAllUserGroups,
  createUserGroup,
  updateUserGroup,
  deleteUserGroup,
  addGroupSupervisor,
  removeGroupSupervisor,
} from "@/services/userGroups";

const mockApiRequest = vi.mocked(apiRequest);
beforeEach(() => vi.clearAllMocks());

describe("getAllUserGroups", () => {
  it("requests the user-groups list and returns the array", async () => {
    const groups = [{ id: "1" }];
    mockApiRequest.mockResolvedValue(groups as never);

    const result = await getAllUserGroups();

    expect(mockApiRequest).toHaveBeenCalledWith("GET", "user-groups/");
    expect(result).toBe(groups);
  });

  it("throws when the response is null (e.g. 403)", async () => {
    mockApiRequest.mockResolvedValue(null as never);

    await expect(getAllUserGroups()).rejects.toThrow("Failed to fetch user groups");
  });

  it("throws when the response is not an array", async () => {
    mockApiRequest.mockResolvedValue({ not: "array" } as never);

    await expect(getAllUserGroups()).rejects.toThrow("Failed to fetch user groups");
  });

  it("propagates errors", async () => {
    mockApiRequest.mockRejectedValue(new Error("boom"));

    await expect(getAllUserGroups()).rejects.toThrow("boom");
  });
});

describe("createUserGroup", () => {
  it("posts the group data and returns the created group", async () => {
    const created = { id: "new" };
    mockApiRequest.mockResolvedValue(created as never);

    const result = await createUserGroup({ name: "team" });

    expect(mockApiRequest).toHaveBeenCalledWith("POST", "user-groups/", { name: "team" });
    expect(result).toBe(created);
  });

  it("throws when the response is null", async () => {
    mockApiRequest.mockResolvedValue(null as never);

    await expect(createUserGroup({ name: "x" })).rejects.toThrow(
      "Failed to create user group",
    );
  });
});

describe("updateUserGroup", () => {
  it("patches the group data and returns the updated group", async () => {
    const updated = { id: "5", name: "team2" };
    mockApiRequest.mockResolvedValue(updated as never);

    const result = await updateUserGroup("5", { name: "team2" });

    expect(mockApiRequest).toHaveBeenCalledWith("PATCH", "user-groups/5", { name: "team2" });
    expect(result).toBe(updated);
  });

  it("throws when the response is null", async () => {
    mockApiRequest.mockResolvedValue(null as never);

    await expect(updateUserGroup("5", {})).rejects.toThrow(
      "Failed to update user group",
    );
  });
});

describe("deleteUserGroup", () => {
  it("deletes the group by id and resolves to undefined", async () => {
    mockApiRequest.mockResolvedValue(undefined as never);

    const result = await deleteUserGroup("5");

    expect(mockApiRequest).toHaveBeenCalledWith("DELETE", "user-groups/5");
    expect(result).toBeUndefined();
  });

  it("propagates errors", async () => {
    mockApiRequest.mockRejectedValue(new Error("boom"));

    await expect(deleteUserGroup("5")).rejects.toThrow("boom");
  });
});

describe("addGroupSupervisor", () => {
  it("posts to the supervisors endpoint and resolves to undefined", async () => {
    mockApiRequest.mockResolvedValue(undefined as never);

    const result = await addGroupSupervisor("g1", "u1");

    expect(mockApiRequest).toHaveBeenCalledWith(
      "POST",
      "user-groups/g1/supervisors/u1",
    );
    expect(result).toBeUndefined();
  });

  it("propagates errors", async () => {
    mockApiRequest.mockRejectedValue(new Error("boom"));

    await expect(addGroupSupervisor("g1", "u1")).rejects.toThrow("boom");
  });
});

describe("removeGroupSupervisor", () => {
  it("deletes from the supervisors endpoint and resolves to undefined", async () => {
    mockApiRequest.mockResolvedValue(undefined as never);

    const result = await removeGroupSupervisor("g1", "u1");

    expect(mockApiRequest).toHaveBeenCalledWith(
      "DELETE",
      "user-groups/g1/supervisors/u1",
    );
    expect(result).toBeUndefined();
  });

  it("propagates errors", async () => {
    mockApiRequest.mockRejectedValue(new Error("boom"));

    await expect(removeGroupSupervisor("g1", "u1")).rejects.toThrow("boom");
  });
});
