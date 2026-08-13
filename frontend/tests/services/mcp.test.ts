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
import { discoverMCPTools } from "@/services/mcp";

const mockApiRequest = vi.mocked(apiRequest);

beforeEach(() => {
  vi.clearAllMocks();
  vi.spyOn(console, "error").mockImplementation(() => {});
});

describe("discoverMCPTools", () => {
  it("POSTs the connection type + config and returns the discovered tools", async () => {
    const tools = [{ name: "search" }];
    mockApiRequest.mockResolvedValue({ tools } as never);
    const config = { url: "https://mcp.test/sse" };
    const result = await discoverMCPTools("http" as never, config as never);
    expect(mockApiRequest).toHaveBeenCalledWith("POST", "mcp/discover-tools", {
      connection_type: "http",
      connection_config: config,
    });
    expect(result).toEqual(tools);
  });

  it("returns [] when the response has no tools", async () => {
    mockApiRequest.mockResolvedValue({} as never);
    expect(await discoverMCPTools("sse" as never, {} as never)).toEqual([]);
  });

  it("returns [] when the response is null", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    expect(await discoverMCPTools("sse" as never, {} as never)).toEqual([]);
  });

  it("throws for stdio connections without calling the API", async () => {
    await expect(
      discoverMCPTools("stdio" as never, {} as never)
    ).rejects.toThrow("Tool discovery is not available for STDIO connections");
    expect(mockApiRequest).not.toHaveBeenCalled();
  });

  it("re-throws (and logs) on error", async () => {
    mockApiRequest.mockRejectedValue(new Error("boom"));
    await expect(
      discoverMCPTools("http" as never, {} as never)
    ).rejects.toThrow("boom");
  });
});
