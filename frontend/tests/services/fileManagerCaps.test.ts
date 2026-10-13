import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

vi.mock("@/config/api", () => ({
  apiRequest: vi.fn(),
  getApiUrl: vi.fn(async () => "http://localhost/api/"),
  getApiUrlString: "http://localhost/api/",
  formatUploadOrNetworkError: (e: unknown) => (e instanceof Error ? e.message : String(e)),
  API_DEFAULT_TIMEOUT_MS: 1000,
  API_UPLOAD_TIMEOUT_MS: 1000,
  api: { get: vi.fn(), post: vi.fn(), put: vi.fn(), patch: vi.fn(), delete: vi.fn(), request: vi.fn() },
}));

vi.mock("@/services/apiKeys", () => ({
  getApiKeys: vi.fn(),
  revealApiKey: vi.fn(),
}));

import { api } from "@/config/api";
import { getFileManagerCaps } from "@/services/api";

const mockGet = vi.mocked(api.get);

const grantPermissions = (permissions: string[]) =>
  vi.stubGlobal("localStorage", {
    getItem: (key: string) => (key === "permissions" ? JSON.stringify(permissions) : null),
  });

beforeEach(() => vi.clearAllMocks());
afterEach(() => vi.unstubAllGlobals());

describe("getFileManagerCaps", () => {
  it("uses the standard upload without asking when the user may not read file settings", async () => {
    grantPermissions(["read:conversation"]);

    await expect(getFileManagerCaps(true)).resolves.toEqual({ directS3UploadEnabled: false });
    expect(mockGet).not.toHaveBeenCalled();
  });

  it("does not keep the no-permission answer once the permission arrives", async () => {
    grantPermissions(["read:conversation"]);
    await getFileManagerCaps(true);

    grantPermissions(["read:file"]);
    mockGet.mockResolvedValue({ data: { is_active: 1, values: { direct_s3_upload_enabled: true } } } as never);

    await expect(getFileManagerCaps()).resolves.toEqual({ directS3UploadEnabled: true });
    expect(mockGet).toHaveBeenCalledTimes(1);
  });

  it("reads the settings for users holding the permission", async () => {
    grantPermissions(["read:file"]);
    mockGet.mockResolvedValue({ data: { is_active: 1, values: { direct_s3_upload_enabled: true } } } as never);

    await expect(getFileManagerCaps(true)).resolves.toEqual({ directS3UploadEnabled: true });
    expect(mockGet).toHaveBeenCalledWith("http://localhost/api/file-manager/settings", { timeout: 1000 });
  });
});
