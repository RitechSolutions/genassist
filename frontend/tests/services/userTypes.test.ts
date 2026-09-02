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
  getAllUserTypes,
  getUserType,
  createUserType,
  deleteUserType,
  updateUserType,
} from "@/services/userTypes";

const mockApiRequest = vi.mocked(apiRequest);
beforeEach(() => vi.clearAllMocks());

describe("getAllUserTypes", () => {
  it("requests the user-type list and returns it", async () => {
    const types = [{ id: "1" }];
    mockApiRequest.mockResolvedValue(types as never);

    const result = await getAllUserTypes();

    expect(mockApiRequest).toHaveBeenCalledWith("GET", "user-type/");
    expect(result).toBe(types);
  });

  it("falls back to an empty array when the response is null", async () => {
    mockApiRequest.mockResolvedValue(null as never);

    await expect(getAllUserTypes()).resolves.toEqual([]);
  });

  it("propagates errors", async () => {
    mockApiRequest.mockRejectedValue(new Error("boom"));

    await expect(getAllUserTypes()).rejects.toThrow("boom");
  });
});

describe("getUserType", () => {
  it("requests a single user-type by id and returns it", async () => {
    const type = { id: "9" };
    mockApiRequest.mockResolvedValue(type as never);

    const result = await getUserType("9");

    expect(mockApiRequest).toHaveBeenCalledWith("GET", "user-type/9");
    expect(result).toBe(type);
  });

  it("returns null when the response is null", async () => {
    mockApiRequest.mockResolvedValue(null as never);

    await expect(getUserType("9")).resolves.toBeNull();
  });

  it("propagates errors", async () => {
    mockApiRequest.mockRejectedValue(new Error("boom"));

    await expect(getUserType("9")).rejects.toThrow("boom");
  });
});

describe("createUserType", () => {
  it("posts the user-type data and returns the created user-type", async () => {
    const created = { id: "new" };
    mockApiRequest.mockResolvedValue(created as never);

    const result = await createUserType({ name: "internal" });

    expect(mockApiRequest).toHaveBeenCalledWith("POST", "user-type", { name: "internal" });
    expect(result).toBe(created);
  });

  it("throws when the response is null", async () => {
    mockApiRequest.mockResolvedValue(null as never);

    await expect(createUserType({ name: "x" })).rejects.toThrow(
      "Failed to create user type",
    );
  });

  it("propagates errors", async () => {
    mockApiRequest.mockRejectedValue(new Error("boom"));

    await expect(createUserType({ name: "x" })).rejects.toThrow("boom");
  });
});

describe("deleteUserType", () => {
  it("deletes the user-type by id and resolves to undefined", async () => {
    mockApiRequest.mockResolvedValue(undefined as never);

    const result = await deleteUserType("9");

    expect(mockApiRequest).toHaveBeenCalledWith("DELETE", "user-type/9");
    expect(result).toBeUndefined();
  });

  it("propagates errors", async () => {
    mockApiRequest.mockRejectedValue(new Error("boom"));

    await expect(deleteUserType("9")).rejects.toThrow("boom");
  });
});

describe("updateUserType", () => {
  it("patches the user-type data and returns the updated user-type", async () => {
    const updated = { id: "9", name: "external" };
    mockApiRequest.mockResolvedValue(updated as never);

    const result = await updateUserType("9", { name: "external" });

    expect(mockApiRequest).toHaveBeenCalledWith("PATCH", "user-type/9", { name: "external" });
    expect(result).toBe(updated);
  });

  it("throws when the response is null", async () => {
    mockApiRequest.mockResolvedValue(null as never);

    await expect(updateUserType("9", {})).rejects.toThrow(
      "Failed to update user type",
    );
  });

  it("propagates errors", async () => {
    mockApiRequest.mockRejectedValue(new Error("boom"));

    await expect(updateUserType("9", {})).rejects.toThrow("boom");
  });
});
