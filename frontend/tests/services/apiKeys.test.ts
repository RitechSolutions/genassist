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
  getApiKeysPaginated,
  getApiKey,
  createApiKey,
  updateApiKey,
  revokeApiKey,
  rotateApiKey,
  revealApiKey,
  getApiKeys,
} from "@/services/apiKeys";

const mockApiRequest = vi.mocked(apiRequest);
beforeEach(() => vi.clearAllMocks());

describe("getApiKeysPaginated", () => {
  const page = <T,>(items: T[]) => ({
    items,
    total: items.length,
    page: 1,
    page_size: 20,
    total_pages: 1,
  });

  const requestedUrl = () => String(mockApiRequest.mock.calls[0][1]);

  it("defaults to the first page of 20", async () => {
    mockApiRequest.mockResolvedValue(page([{ id: "k1" }]) as never);

    await getApiKeysPaginated();

    expect(mockApiRequest).toHaveBeenCalledWith("GET", "api-keys/list?skip=0&limit=20");
  });

  it("converts page and pageSize into skip and limit", async () => {
    mockApiRequest.mockResolvedValue(page([]) as never);

    await getApiKeysPaginated(3, 10);

    expect(requestedUrl()).toBe("api-keys/list?skip=20&limit=10");
  });

  it("clamps pageSize to the backend maximum of 100", async () => {
    mockApiRequest.mockResolvedValue(page([]) as never);

    await getApiKeysPaginated(1, 500);

    expect(requestedUrl()).toContain("limit=100");
  });

  it("clamps page and pageSize to their minimums", async () => {
    mockApiRequest.mockResolvedValue(page([]) as never);

    await getApiKeysPaginated(0, 0);

    expect(requestedUrl()).toBe("api-keys/list?skip=0&limit=1");
  });

  it("passes a trimmed search term", async () => {
    mockApiRequest.mockResolvedValue(page([]) as never);

    await getApiKeysPaginated(1, 20, "  ana  ");

    expect(requestedUrl()).toBe("api-keys/list?skip=0&limit=20&search=ana");
  });

  it("omits the search param when it is absent or blank", async () => {
    mockApiRequest.mockResolvedValue(page([]) as never);

    await getApiKeysPaginated(1, 20, "   ");
    expect(requestedUrl()).not.toContain("search");

    vi.clearAllMocks();
    mockApiRequest.mockResolvedValue(page([]) as never);
    await getApiKeysPaginated(1, 20, undefined);
    expect(requestedUrl()).not.toContain("search");
  });

  it("returns the paginated body unchanged", async () => {
    const body = page([{ id: "k1" }, { id: "k2" }]);
    mockApiRequest.mockResolvedValue(body as never);

    await expect(getApiKeysPaginated()).resolves.toEqual(body);
  });

  it("returns an empty page when the response is null (403)", async () => {
    mockApiRequest.mockResolvedValue(null as never);

    await expect(getApiKeysPaginated(2, 50)).resolves.toEqual({
      items: [],
      total: 0,
      page: 1,
      page_size: 50,
      total_pages: 0,
    });
  });

  it("propagates non-403 errors", async () => {
    mockApiRequest.mockRejectedValue(new Error("boom"));

    await expect(getApiKeysPaginated()).rejects.toThrow("boom");
  });
});

describe("getApiKey", () => {
  it("requests a single api-key by id and returns it", async () => {
    const key = { id: "k1" };
    mockApiRequest.mockResolvedValue(key as never);

    const result = await getApiKey("k1");

    expect(mockApiRequest).toHaveBeenCalledWith("GET", "api-keys/k1/");
    expect(result).toBe(key);
  });

  it("returns null when the response is null", async () => {
    mockApiRequest.mockResolvedValue(null as never);

    await expect(getApiKey("k1")).resolves.toBeNull();
  });
});

describe("createApiKey", () => {
  it("posts the mapped payload and returns the created key", async () => {
    const created = { id: "new" };
    mockApiRequest.mockResolvedValue(created as never);

    const result = await createApiKey({
      name: "my-key",
      is_active: 1,
      role_ids: ["r1"],
      user_id: "u1",
    });

    expect(mockApiRequest).toHaveBeenCalledWith("POST", "api-keys/", {
      name: "my-key",
      is_active: 1,
      role_ids: ["r1"],
      assigned_user_id: "u1",
      user_id: "u1",
    });
    expect(result).toBe(created);
  });

  it("defaults role_ids to an empty array and includes agent_id/expires_in_days when provided", async () => {
    mockApiRequest.mockResolvedValue({ id: "new" } as never);

    await createApiKey({
      name: "k",
      is_active: 0,
      user_id: "u2",
      agent_id: "a1",
      expires_in_days: 30,
    });

    expect(mockApiRequest).toHaveBeenCalledWith("POST", "api-keys/", {
      name: "k",
      is_active: 0,
      role_ids: [],
      assigned_user_id: "u2",
      user_id: "u2",
      agent_id: "a1",
      expires_in_days: 30,
    });
  });

  it("throws when the response is null", async () => {
    mockApiRequest.mockResolvedValue(null as never);

    await expect(createApiKey({ name: "k" })).rejects.toThrow(
      "Failed to create API key",
    );
  });
});

describe("updateApiKey", () => {
  it("patches the mapped payload with boolean is_active and returns the key", async () => {
    const updated = { id: "k1" };
    mockApiRequest.mockResolvedValue(updated as never);

    const result = await updateApiKey("k1", {
      name: "renamed",
      is_active: 1 as never,
      user_id: "u1",
    });

    expect(mockApiRequest).toHaveBeenCalledWith("PATCH", "api-keys/k1/", {
      name: "renamed",
      is_active: true,
      user_id: "u1",
    });
    expect(result).toBe(updated);
  });

  it("includes role_ids, agent_id and expires_in_days when provided", async () => {
    mockApiRequest.mockResolvedValue({ id: "k1" } as never);

    await updateApiKey("k1", {
      name: "k",
      is_active: 0 as never,
      user_id: "u1",
      role_ids: ["r1", "r2"],
      agent_id: "a1",
      expires_in_days: 7,
    });

    expect(mockApiRequest).toHaveBeenCalledWith("PATCH", "api-keys/k1/", {
      name: "k",
      is_active: false,
      user_id: "u1",
      role_ids: ["r1", "r2"],
      agent_id: "a1",
      expires_in_days: 7,
    });
  });

  it("throws when the response is null", async () => {
    mockApiRequest.mockResolvedValue(null as never);

    await expect(updateApiKey("k1", {})).rejects.toThrow("Failed to update API key");
  });
});

describe("revokeApiKey", () => {
  it("deletes the api-key by id and resolves to undefined", async () => {
    mockApiRequest.mockResolvedValue(undefined as never);

    const result = await revokeApiKey("k1");

    expect(mockApiRequest).toHaveBeenCalledWith("DELETE", "api-keys/k1/");
    expect(result).toBeUndefined();
  });

  it("propagates errors", async () => {
    mockApiRequest.mockRejectedValue(new Error("boom"));

    await expect(revokeApiKey("k1")).rejects.toThrow("boom");
  });
});

describe("rotateApiKey", () => {
  it("posts to the rotate endpoint with the default overlap and returns the key", async () => {
    const rotated = { id: "k1" };
    mockApiRequest.mockResolvedValue(rotated as never);

    const result = await rotateApiKey("k1");

    expect(mockApiRequest).toHaveBeenCalledWith("POST", "api-keys/k1/rotate", {
      overlap_seconds: 0,
    });
    expect(result).toBe(rotated);
  });

  it("passes a custom overlap value", async () => {
    mockApiRequest.mockResolvedValue({ id: "k1" } as never);

    await rotateApiKey("k1", 60);

    expect(mockApiRequest).toHaveBeenCalledWith("POST", "api-keys/k1/rotate", {
      overlap_seconds: 60,
    });
  });

  it("throws when the response is null", async () => {
    mockApiRequest.mockResolvedValue(null as never);

    await expect(rotateApiKey("k1")).rejects.toThrow("Failed to rotate API key");
  });
});

describe("revealApiKey", () => {
  it("posts to the reveal endpoint and returns the key", async () => {
    const revealed = { id: "k1", key: "secret" };
    mockApiRequest.mockResolvedValue(revealed as never);

    const result = await revealApiKey("k1");

    expect(mockApiRequest).toHaveBeenCalledWith("POST", "api-keys/k1/reveal");
    expect(result).toBe(revealed);
  });

  it("throws when the response is null", async () => {
    mockApiRequest.mockResolvedValue(null as never);

    await expect(revealApiKey("k1")).rejects.toThrow("Failed to reveal API key");
  });
});

describe("getApiKeys", () => {
  it("requests the plain list when no userId is provided", async () => {
    const keys = [{ id: "k1" }];
    mockApiRequest.mockResolvedValue(keys as never);

    const result = await getApiKeys();

    expect(mockApiRequest).toHaveBeenCalledWith("GET", "api-keys/");
    expect(result).toBe(keys);
  });

  it("appends an encoded user_id query when a userId is provided", async () => {
    mockApiRequest.mockResolvedValue([] as never);

    await getApiKeys("user with space");

    expect(mockApiRequest).toHaveBeenCalledWith(
      "GET",
      "api-keys/?user_id=user%20with%20space",
    );
  });

  it("returns an empty array when the response is null", async () => {
    mockApiRequest.mockResolvedValue(null as never);

    await expect(getApiKeys()).resolves.toEqual([]);
  });

  it("returns an empty array when the response is not an array", async () => {
    mockApiRequest.mockResolvedValue({ not: "array" } as never);

    await expect(getApiKeys()).resolves.toEqual([]);
  });
});
