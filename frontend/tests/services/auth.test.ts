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
  isTokenExpired,
  completeMicrosoftSso,
  getAuthMe,
} from "@/services/auth";

const mockApiRequest = vi.mocked(apiRequest);
beforeEach(() => vi.clearAllMocks());

// Build a base64url-encoded JWT payload segment (jwt-decode compatible).
function base64UrlPayload(payload: unknown): string {
  return Buffer.from(JSON.stringify(payload))
    .toString("base64")
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/, "");
}

function makeJwt(payload: unknown): string {
  return `header.${base64UrlPayload(payload)}.signature`;
}

describe("isTokenExpired", () => {
  it("returns false for a token whose exp is in the future", () => {
    const token = makeJwt({ exp: Math.floor(Date.now() / 1000) + 3600 });
    expect(isTokenExpired(token)).toBe(false);
  });

  it("returns true for a token whose exp is in the past", () => {
    const token = makeJwt({ exp: Math.floor(Date.now() / 1000) - 3600 });
    expect(isTokenExpired(token)).toBe(true);
  });

  it("returns true for a malformed / undecodable token", () => {
    expect(isTokenExpired("not-a-jwt")).toBe(true);
  });
});

describe("completeMicrosoftSso", () => {
  it("posts the sso code and returns the tokens", async () => {
    const tokens = {
      access_token: "at",
      refresh_token: "rt",
      token_type: "Bearer",
    };
    mockApiRequest.mockResolvedValue(tokens as never);

    const result = await completeMicrosoftSso("sso-code");

    expect(mockApiRequest).toHaveBeenCalledWith(
      "POST",
      "auth/sso/microsoft/complete",
      { code: "sso-code" },
    );
    expect(result).toBe(tokens);
  });

  it("returns null when the response is null", async () => {
    mockApiRequest.mockResolvedValue(null as never);

    await expect(completeMicrosoftSso("sso-code")).resolves.toBeNull();
  });

  it("propagates errors", async () => {
    mockApiRequest.mockRejectedValue(new Error("boom"));

    await expect(completeMicrosoftSso("sso-code")).rejects.toThrow("boom");
  });
});

describe("getAuthMe", () => {
  it("requests the current user and returns it", async () => {
    const user = { id: "u1", username: "alice" };
    mockApiRequest.mockResolvedValue(user as never);

    const result = await getAuthMe();

    expect(mockApiRequest).toHaveBeenCalledWith("GET", "/auth/me");
    expect(result).toBe(user);
  });

  it("propagates errors", async () => {
    mockApiRequest.mockRejectedValue(new Error("boom"));

    await expect(getAuthMe()).rejects.toThrow("boom");
  });
});
