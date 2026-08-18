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
  getAllUsers,
  getUser,
  createUser,
  updateUser,
  deleteUser,
  restoreUser,
} from "@/services/users";

const mockApiRequest = vi.mocked(apiRequest);
beforeEach(() => vi.clearAllMocks());

describe("getAllUsers", () => {
  it("requests the plain user list and returns it", async () => {
    const users = [{ id: "1" }, { id: "2" }];
    mockApiRequest.mockResolvedValue(users as never);

    const result = await getAllUsers();

    expect(mockApiRequest).toHaveBeenCalledWith("GET", "user/");
    expect(result).toBe(users);
  });

  it("uses the deleted_only query when deletedOnly is true", async () => {
    mockApiRequest.mockResolvedValue([] as never);

    await getAllUsers({ deletedOnly: true });

    expect(mockApiRequest).toHaveBeenCalledWith("GET", "user/?deleted_only=true");
  });

  it("does not use the deleted_only query when deletedOnly is not true", async () => {
    mockApiRequest.mockResolvedValue([] as never);

    await getAllUsers({ deletedOnly: false });

    expect(mockApiRequest).toHaveBeenCalledWith("GET", "user/");
  });

  it("falls back to an empty array when the response is null", async () => {
    mockApiRequest.mockResolvedValue(null as never);

    await expect(getAllUsers()).resolves.toEqual([]);
  });

  it("propagates errors", async () => {
    mockApiRequest.mockRejectedValue(new Error("boom"));

    await expect(getAllUsers()).rejects.toThrow("boom");
  });
});

describe("getUser", () => {
  it("requests a single user by id and returns it", async () => {
    const user = { id: "42" };
    mockApiRequest.mockResolvedValue(user as never);

    const result = await getUser("42");

    expect(mockApiRequest).toHaveBeenCalledWith("GET", "user/42");
    expect(result).toBe(user);
  });

  it("returns null when the response is null", async () => {
    mockApiRequest.mockResolvedValue(null as never);

    await expect(getUser("42")).resolves.toBeNull();
  });

  it("propagates errors", async () => {
    mockApiRequest.mockRejectedValue(new Error("boom"));

    await expect(getUser("42")).rejects.toThrow("boom");
  });
});

describe("createUser", () => {
  it("posts the mapped payload and returns the created user", async () => {
    const created = { id: "new" };
    mockApiRequest.mockResolvedValue(created as never);

    const userData = {
      username: "alice",
      email: "a@b.com",
      password: "pw",
      is_active: true,
      user_type_id: "ut1",
      role_ids: ["r1", "r2"],
      group_id: "g1",
    };

    const result = await createUser(userData as never);

    expect(mockApiRequest).toHaveBeenCalledWith("POST", "user", {
      username: "alice",
      email: "a@b.com",
      password: "pw",
      is_active: true,
      user_type_id: "ut1",
      role_ids: ["r1", "r2"],
      group_id: "g1",
    });
    expect(result).toBe(created);
  });

  it("defaults group_id to null and includes entra_oid when provided", async () => {
    mockApiRequest.mockResolvedValue({ id: "new" } as never);

    const userData = {
      username: "bob",
      email: "b@b.com",
      password: "pw",
      is_active: false,
      user_type_id: "ut2",
      role_ids: [],
      entra_oid: "oid-1",
    };

    await createUser(userData as never);

    expect(mockApiRequest).toHaveBeenCalledWith("POST", "user", {
      username: "bob",
      email: "b@b.com",
      password: "pw",
      is_active: false,
      user_type_id: "ut2",
      role_ids: [],
      group_id: null,
      entra_oid: "oid-1",
    });
  });

  it("throws when the response is null", async () => {
    mockApiRequest.mockResolvedValue(null as never);

    await expect(createUser({ username: "x" } as never)).rejects.toThrow(
      "Failed to create user",
    );
  });

  it("propagates errors", async () => {
    mockApiRequest.mockRejectedValue(new Error("boom"));

    await expect(createUser({ username: "x" } as never)).rejects.toThrow("boom");
  });
});

describe("updateUser", () => {
  it("puts the partial payload and returns the updated user", async () => {
    const updated = { id: "42", username: "alice2" };
    mockApiRequest.mockResolvedValue(updated as never);

    const result = await updateUser("42", { username: "alice2" });

    expect(mockApiRequest).toHaveBeenCalledWith("PUT", "user/42", {
      username: "alice2",
    });
    expect(result).toBe(updated);
  });

  it("throws when the response is null", async () => {
    mockApiRequest.mockResolvedValue(null as never);

    await expect(updateUser("42", {})).rejects.toThrow("Failed to update user");
  });

  it("propagates errors", async () => {
    mockApiRequest.mockRejectedValue(new Error("boom"));

    await expect(updateUser("42", {})).rejects.toThrow("boom");
  });
});

describe("deleteUser", () => {
  it("deletes the user by id and resolves to undefined", async () => {
    mockApiRequest.mockResolvedValue(undefined as never);

    const result = await deleteUser("42");

    expect(mockApiRequest).toHaveBeenCalledWith("DELETE", "user/42");
    expect(result).toBeUndefined();
  });

  it("propagates errors", async () => {
    mockApiRequest.mockRejectedValue(new Error("boom"));

    await expect(deleteUser("42")).rejects.toThrow("boom");
  });
});

describe("restoreUser", () => {
  it("posts to the restore endpoint and returns the restored user", async () => {
    const restored = { id: "42" };
    mockApiRequest.mockResolvedValue(restored as never);

    const result = await restoreUser("42");

    expect(mockApiRequest).toHaveBeenCalledWith("POST", "user/42/restore");
    expect(result).toBe(restored);
  });

  it("throws when the response is null", async () => {
    mockApiRequest.mockResolvedValue(null as never);

    await expect(restoreUser("42")).rejects.toThrow("Failed to restore user");
  });

  it("propagates errors", async () => {
    mockApiRequest.mockRejectedValue(new Error("boom"));

    await expect(restoreUser("42")).rejects.toThrow("boom");
  });
});
