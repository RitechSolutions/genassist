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
  listDirectory,
  readFile,
  writeFile,
  deleteFile,
  createFolder,
  deleteFolder,
  checkPathExists,
} from "@/services/smbShareFolderService";

const mockApiRequest = vi.mocked(apiRequest);
beforeEach(() => vi.clearAllMocks());

describe("listDirectory", () => {
  it("POSTs to smb/list and returns the entries", async () => {
    const params = { smb_host: "h", subpath: "docs", only_files: true };
    const entries = ["a.txt", "b.txt"];
    mockApiRequest.mockResolvedValue(entries as never);

    const result = await listDirectory(params);

    expect(mockApiRequest).toHaveBeenCalledWith("POST", "smb-share/smb/list", params);
    expect(result).toEqual(entries);
  });

  it("returns an empty array when the response is falsy", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    await expect(listDirectory({})).resolves.toEqual([]);
  });

  it("rethrows on error", async () => {
    mockApiRequest.mockRejectedValue(new Error("list-fail"));
    await expect(listDirectory({})).rejects.toThrow("list-fail");
  });
});

describe("readFile", () => {
  it("POSTs to smb/read and returns the file contents", async () => {
    const params = { smb_host: "h", filepath: "a.txt" };
    mockApiRequest.mockResolvedValue("file-contents" as never);

    const result = await readFile(params);

    expect(mockApiRequest).toHaveBeenCalledWith("POST", "smb-share/smb/read", params);
    expect(result).toBe("file-contents");
  });

  it("rethrows on error", async () => {
    mockApiRequest.mockRejectedValue(new Error("read-fail"));
    await expect(readFile({ filepath: "a.txt" })).rejects.toThrow("read-fail");
  });
});

describe("writeFile", () => {
  it("POSTs to smb/write and resolves on a truthy response", async () => {
    const payload = { filepath: "a.txt", content: "hi" };
    mockApiRequest.mockResolvedValue({ ok: true } as never);

    await expect(writeFile(payload)).resolves.toBeUndefined();
    expect(mockApiRequest).toHaveBeenCalledWith("POST", "smb-share/smb/write", payload);
  });

  it("throws when the response is falsy", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    await expect(writeFile({ filepath: "a.txt" })).rejects.toThrow("Failed to write SMB file");
  });
});

describe("deleteFile", () => {
  it("DELETEs smb/file and resolves on a truthy response", async () => {
    const payload = { filepath: "a.txt" };
    mockApiRequest.mockResolvedValue({ ok: true } as never);

    await expect(deleteFile(payload)).resolves.toBeUndefined();
    expect(mockApiRequest).toHaveBeenCalledWith("DELETE", "smb-share/smb/file", payload);
  });

  it("throws when the response is falsy", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    await expect(deleteFile({ filepath: "a.txt" })).rejects.toThrow("Failed to delete SMB file");
  });
});

describe("createFolder", () => {
  it("POSTs to smb/folder and resolves on a truthy response", async () => {
    const payload = { folderpath: "docs" };
    mockApiRequest.mockResolvedValue({ ok: true } as never);

    await expect(createFolder(payload)).resolves.toBeUndefined();
    expect(mockApiRequest).toHaveBeenCalledWith("POST", "smb-share/smb/folder", payload);
  });

  it("throws when the response is falsy", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    await expect(createFolder({ folderpath: "docs" })).rejects.toThrow(
      "Failed to create SMB folder",
    );
  });
});

describe("deleteFolder", () => {
  it("DELETEs smb/folder and resolves on a truthy response", async () => {
    const payload = { folderpath: "docs" };
    mockApiRequest.mockResolvedValue({ ok: true } as never);

    await expect(deleteFolder(payload)).resolves.toBeUndefined();
    expect(mockApiRequest).toHaveBeenCalledWith("DELETE", "smb-share/smb/folder", payload);
  });

  it("throws when the response is falsy", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    await expect(deleteFolder({ folderpath: "docs" })).rejects.toThrow(
      "Failed to delete SMB folder",
    );
  });
});

describe("checkPathExists", () => {
  it("POSTs to smb/exists and returns the exists flag", async () => {
    const params = { path: "a.txt" };
    mockApiRequest.mockResolvedValue({ exists: true } as never);

    const result = await checkPathExists(params);

    expect(mockApiRequest).toHaveBeenCalledWith("POST", "smb-share/smb/exists", params);
    expect(result).toBe(true);
  });

  it("returns false when the response is falsy", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    await expect(checkPathExists({ path: "a.txt" })).resolves.toBe(false);
  });

  it("rethrows on error", async () => {
    mockApiRequest.mockRejectedValue(new Error("exists-fail"));
    await expect(checkPathExists({ path: "a.txt" })).rejects.toThrow("exists-fail");
  });
});
