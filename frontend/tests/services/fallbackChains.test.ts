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
  getAllFallbackChains,
  getFallbackChainsMinimal,
  getFallbackChain,
  createFallbackChain,
  updateFallbackChain,
  deleteFallbackChain,
} from "@/services/fallbackChains";

const mockApiRequest = vi.mocked(apiRequest);
beforeEach(() => vi.clearAllMocks());

describe("fallbackChains service", () => {
  it("getAllFallbackChains GETs the collection and passes the result through", async () => {
    const rows = [{ id: "fc1" }];
    mockApiRequest.mockResolvedValue(rows as never);
    const result = await getAllFallbackChains();
    expect(mockApiRequest).toHaveBeenCalledWith("GET", "fallback-chains/");
    expect(result).toEqual(rows);
  });

  it("getFallbackChainsMinimal GETs the minimal list", async () => {
    await getFallbackChainsMinimal();
    expect(mockApiRequest).toHaveBeenCalledWith("GET", "fallback-chains/minimal");
  });

  it("getFallbackChain GETs a single chain by id and passes it through", async () => {
    const chain = { id: "fc2" };
    mockApiRequest.mockResolvedValue(chain as never);
    const result = await getFallbackChain("fc2");
    expect(mockApiRequest).toHaveBeenCalledWith("GET", "fallback-chains/fc2");
    expect(result).toEqual(chain);
  });

  describe("createFallbackChain", () => {
    it("POSTs a deep-cloned payload to the collection", async () => {
      const data = { name: "Chain", steps: [{ model: "gpt" }] };
      await createFallbackChain(data as never);
      expect(mockApiRequest).toHaveBeenCalledWith("POST", "fallback-chains", data);
      // JSON round-trip produces a new object, not the same reference.
      expect(mockApiRequest.mock.calls[0][2]).not.toBe(data);
    });

    it("strips undefined properties via the JSON round-trip", async () => {
      const data = { name: "Chain", note: undefined };
      await createFallbackChain(data as never);
      expect(mockApiRequest).toHaveBeenCalledWith("POST", "fallback-chains", { name: "Chain" });
    });
  });

  it("updateFallbackChain PATCHes a deep-cloned payload to the id endpoint", async () => {
    const data = { name: "Renamed" };
    await updateFallbackChain("fc3", data as never);
    expect(mockApiRequest).toHaveBeenCalledWith("PATCH", "fallback-chains/fc3", data);
    expect(mockApiRequest.mock.calls[0][2]).not.toBe(data);
  });

  it("deleteFallbackChain DELETEs by id", async () => {
    await deleteFallbackChain("fc4");
    expect(mockApiRequest).toHaveBeenCalledWith("DELETE", "fallback-chains/fc4");
  });
});
