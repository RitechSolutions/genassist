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
  getAllMCPServers,
  getMCPServer,
  createMCPServer,
  updateMCPServer,
  deleteMCPServer,
} from "@/services/mcpServer";

const mockApiRequest = vi.mocked(apiRequest);
beforeEach(() => vi.clearAllMocks());

describe("getAllMCPServers", () => {
  it("GETs mcp-servers and normalizes each server", async () => {
    mockApiRequest.mockResolvedValue([
      { id: "1", name: "a", auth_type: "oauth2" },
      { id: "2", name: "b", auth_type: "basic", auth_values: { key: "v" } },
    ] as never);
    const result = await getAllMCPServers();
    expect(mockApiRequest).toHaveBeenCalledWith("GET", "mcp-servers");
    expect(result).toEqual([
      { id: "1", name: "a", auth_type: "oauth2", auth_values: {} },
      { id: "2", name: "b", auth_type: "api_key", auth_values: { key: "v" } },
    ]);
  });

  it("returns [] when the response is not an array", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    expect(await getAllMCPServers()).toEqual([]);
  });

  it("re-throws on error", async () => {
    mockApiRequest.mockRejectedValue(new Error("boom"));
    await expect(getAllMCPServers()).rejects.toThrow("boom");
  });
});

describe("getMCPServer", () => {
  it("GETs mcp-servers/:id and normalizes the server", async () => {
    mockApiRequest.mockResolvedValue({ id: "5", name: "a", auth_type: "oauth2" } as never);
    const result = await getMCPServer("5");
    expect(mockApiRequest).toHaveBeenCalledWith("GET", "mcp-servers/5");
    expect(result).toEqual({ id: "5", name: "a", auth_type: "oauth2", auth_values: {} });
  });

  it("returns null when the response is falsy", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    expect(await getMCPServer("5")).toBeNull();
  });
});

describe("createMCPServer", () => {
  it("POSTs mcp-servers and returns the normalized server", async () => {
    mockApiRequest.mockResolvedValue({ id: "1", name: "a", auth_type: "weird" } as never);
    const payload = { name: "a", url: "https://x.test" };
    const result = await createMCPServer(payload as never);
    expect(mockApiRequest).toHaveBeenCalledWith("POST", "mcp-servers", payload);
    expect(result).toEqual({ id: "1", name: "a", auth_type: "api_key", auth_values: {} });
  });

  it("throws when the response is falsy", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    await expect(createMCPServer({ name: "a" } as never)).rejects.toThrow(
      "Failed to create MCP server"
    );
  });
});

describe("updateMCPServer", () => {
  it("PUTs mcp-servers/:id and returns the normalized server", async () => {
    mockApiRequest.mockResolvedValue({ id: "2", name: "b", auth_type: "oauth2" } as never);
    const payload = { name: "b" };
    const result = await updateMCPServer("2", payload as never);
    expect(mockApiRequest).toHaveBeenCalledWith("PUT", "mcp-servers/2", payload);
    expect(result).toEqual({ id: "2", name: "b", auth_type: "oauth2", auth_values: {} });
  });

  it("throws when the response is falsy", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    await expect(updateMCPServer("2", { name: "b" } as never)).rejects.toThrow(
      "Failed to update MCP server"
    );
  });
});

describe("deleteMCPServer", () => {
  it("DELETEs mcp-servers/:id", async () => {
    mockApiRequest.mockResolvedValue(undefined as never);
    await deleteMCPServer("3");
    expect(mockApiRequest).toHaveBeenCalledWith("DELETE", "mcp-servers/3");
  });

  it("re-throws on error", async () => {
    mockApiRequest.mockRejectedValue(new Error("boom"));
    await expect(deleteMCPServer("3")).rejects.toThrow("boom");
  });
});
