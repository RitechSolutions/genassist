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
import { fetchRecordings } from "@/services/recordings";

const mockApiRequest = vi.mocked(apiRequest);
beforeEach(() => vi.clearAllMocks());

describe("fetchRecordings", () => {
  it("GETs /audio/recordings and returns the recordings array", async () => {
    const recordings = [{ id: "r1" }];
    mockApiRequest.mockResolvedValue({ recordings } as never);

    const result = await fetchRecordings();

    expect(mockApiRequest).toHaveBeenCalledWith("get", "/audio/recordings");
    expect(result).toEqual(recordings);
  });

  it("returns null when the response is null", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    await expect(fetchRecordings()).resolves.toBeNull();
  });

  it("returns null when the recordings field is absent", async () => {
    mockApiRequest.mockResolvedValue({} as never);
    await expect(fetchRecordings()).resolves.toBeNull();
  });
});
