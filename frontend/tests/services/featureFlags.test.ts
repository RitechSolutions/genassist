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
  getFeatureFlags,
  getFeatureFlag,
  createFeatureFlag,
  updateFeatureFlag,
  deleteFeatureFlag,
} from "@/services/featureFlags";

const mockApiRequest = vi.mocked(apiRequest);
beforeEach(() => vi.clearAllMocks());

describe("getFeatureFlags", () => {
  it("GETs feature-flags/ and returns the array", async () => {
    const flags = [{ id: "1", key: "beta" }];
    mockApiRequest.mockResolvedValue(flags as never);
    const result = await getFeatureFlags();
    expect(mockApiRequest).toHaveBeenCalledWith("GET", "feature-flags/");
    expect(result).toEqual(flags);
  });

  it("returns [] when the response is falsy", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    expect(await getFeatureFlags()).toEqual([]);
  });
});

describe("getFeatureFlag", () => {
  it("GETs feature-flags/:id and returns the flag", async () => {
    const flag = { id: "9", key: "beta" };
    mockApiRequest.mockResolvedValue(flag as never);
    const result = await getFeatureFlag("9");
    expect(mockApiRequest).toHaveBeenCalledWith("GET", "feature-flags/9");
    expect(result).toEqual(flag);
  });

  it("passes null through", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    expect(await getFeatureFlag("9")).toBeNull();
  });
});

describe("createFeatureFlag", () => {
  it("POSTs a shallow copy of the data and returns the flag", async () => {
    const created = { id: "1", key: "beta" };
    mockApiRequest.mockResolvedValue(created as never);
    const data = { key: "beta", enabled: true };
    const result = await createFeatureFlag(data as never);
    expect(mockApiRequest).toHaveBeenCalledWith("POST", "feature-flags", {
      key: "beta",
      enabled: true,
    });
    expect(result).toEqual(created);
  });
});

describe("updateFeatureFlag", () => {
  it("PATCHes feature-flags/:id with a shallow copy of the data", async () => {
    const updated = { id: "3", key: "beta" };
    mockApiRequest.mockResolvedValue(updated as never);
    const result = await updateFeatureFlag("3", { enabled: false } as never);
    expect(mockApiRequest).toHaveBeenCalledWith("PATCH", "feature-flags/3", {
      enabled: false,
    });
    expect(result).toEqual(updated);
  });
});

describe("deleteFeatureFlag", () => {
  it("DELETEs feature-flags/:id", async () => {
    mockApiRequest.mockResolvedValue(undefined as never);
    await deleteFeatureFlag("4");
    expect(mockApiRequest).toHaveBeenCalledWith("DELETE", "feature-flags/4");
  });
});
