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
import { getRegistrationStatus } from "@/services/registration";

const mockApiRequest = vi.mocked(apiRequest);
beforeEach(() => vi.clearAllMocks());

describe("getRegistrationStatus", () => {
  it("requests the registration id and returns the response", async () => {
    const response = { registration_id: "reg-1", is_new: true };
    mockApiRequest.mockResolvedValue(response as never);

    const result = await getRegistrationStatus();

    expect(mockApiRequest).toHaveBeenCalledWith(
      "GET",
      "public-registration/registration-id",
    );
    expect(result).toBe(response);
  });

  it("falls back to a default response when the response is null", async () => {
    mockApiRequest.mockResolvedValue(null as never);

    await expect(getRegistrationStatus()).resolves.toEqual({
      registration_id: null,
      is_new: false,
    });
  });

  it("falls back to a default response on error", async () => {
    mockApiRequest.mockRejectedValue(new Error("boom"));

    await expect(getRegistrationStatus()).resolves.toEqual({
      registration_id: null,
      is_new: false,
    });
  });
});
