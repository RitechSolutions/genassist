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
  listFileManagerFiles,
  getFileManagerSettings,
  listFiles,
  getFileBase64,
} from "@/services/fileManager";

const mockApiRequest = vi.mocked(apiRequest);
beforeEach(() => vi.clearAllMocks());

describe("listFileManagerFiles", () => {
  it("GETs the bare files path when no params are given and returns the data", async () => {
    const rows = [{ id: "f1" }];
    mockApiRequest.mockResolvedValue(rows);

    const result = await listFileManagerFiles();

    expect(mockApiRequest).toHaveBeenCalledWith("GET", "file-manager/files");
    expect(result).toBe(rows);
  });

  it("coerces a null apiRequest result to an empty array", async () => {
    mockApiRequest.mockResolvedValue(null);

    const result = await listFileManagerFiles();

    expect(result).toEqual([]);
  });

  it("builds the full query string in storage_provider/limit/offset/tag order", async () => {
    mockApiRequest.mockResolvedValue([]);

    await listFileManagerFiles({
      storage_provider: "s3",
      limit: 10,
      offset: 5,
      tag: "invoices",
    });

    expect(mockApiRequest).toHaveBeenCalledWith(
      "GET",
      "file-manager/files?storage_provider=s3&limit=10&offset=5&tag=invoices"
    );
  });

  it("includes limit and offset when they are zero", async () => {
    mockApiRequest.mockResolvedValue([]);

    await listFileManagerFiles({ limit: 0, offset: 0 });

    expect(mockApiRequest).toHaveBeenCalledWith("GET", "file-manager/files?limit=0&offset=0");
  });

  it("omits empty-string storage_provider and tag", async () => {
    mockApiRequest.mockResolvedValue([]);

    await listFileManagerFiles({ storage_provider: "", tag: "", limit: 3 });

    expect(mockApiRequest).toHaveBeenCalledWith("GET", "file-manager/files?limit=3");
  });
});

describe("getFileManagerSettings", () => {
  it("GETs the settings endpoint and returns the value", async () => {
    const settings = { id: "s", name: "fm", type: "settings", is_active: 1 };
    mockApiRequest.mockResolvedValue(settings);

    const result = await getFileManagerSettings();

    expect(mockApiRequest).toHaveBeenCalledWith("GET", "file-manager/settings");
    expect(result).toBe(settings);
  });

  it("returns null when the request rejects", async () => {
    mockApiRequest.mockRejectedValue(new Error("boom"));

    const result = await getFileManagerSettings();

    expect(result).toBeNull();
  });
});

describe("listFiles", () => {
  it("GETs the bare files path with no params and returns the raw result", async () => {
    mockApiRequest.mockResolvedValue(null);

    const result = await listFiles();

    expect(mockApiRequest).toHaveBeenCalledWith("GET", "file-manager/files");
    expect(result).toBeNull();
  });

  it("builds the query string from provided params", async () => {
    const rows = [{ id: "x" }];
    mockApiRequest.mockResolvedValue(rows);

    const result = await listFiles({
      storage_provider: "local",
      limit: 50,
      offset: 100,
      tag: "docs",
    });

    expect(mockApiRequest).toHaveBeenCalledWith(
      "GET",
      "file-manager/files?storage_provider=local&limit=50&offset=100&tag=docs"
    );
    expect(result).toBe(rows);
  });

  it("omits a falsy storage_provider but keeps a zero limit/offset", async () => {
    mockApiRequest.mockResolvedValue([]);

    await listFiles({ storage_provider: "", limit: 0, offset: 0 });

    expect(mockApiRequest).toHaveBeenCalledWith("GET", "file-manager/files?limit=0&offset=0");
  });
});

describe("getFileBase64", () => {
  it("GETs the base64 endpoint for a file id", async () => {
    const payload = { file_id: "f1", name: "a.png", content: "AAAA" };
    mockApiRequest.mockResolvedValue(payload);

    const result = await getFileBase64("f1");

    expect(mockApiRequest).toHaveBeenCalledWith("GET", "file-manager/files/f1/base64");
    expect(result).toBe(payload);
  });
});
