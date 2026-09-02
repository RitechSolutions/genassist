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
  getAllAppSettings,
  getAppSetting,
  createAppSetting,
  updateAppSetting,
  deleteAppSetting,
  testAppSettingConnection,
  getAppSettingsFormSchemas,
  getSecuritySettings,
  updateSecuritySettings,
  updateFileManagerSettings,
} from "@/services/appSettings";

const mockApiRequest = vi.mocked(apiRequest);
beforeEach(() => vi.clearAllMocks());

describe("getAllAppSettings", () => {
  it("requests app-settings/ and returns the array", async () => {
    const rows = [{ id: "1", name: "A" }];
    mockApiRequest.mockResolvedValue(rows as never);
    const result = await getAllAppSettings();
    expect(mockApiRequest).toHaveBeenCalledWith("GET", "app-settings/");
    expect(result).toEqual(rows);
  });

  it("returns [] when the response is null", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    expect(await getAllAppSettings()).toEqual([]);
  });

  it("returns [] when the response is not an array", async () => {
    mockApiRequest.mockResolvedValue({ not: "an array" } as never);
    expect(await getAllAppSettings()).toEqual([]);
  });

  it("re-throws on error", async () => {
    mockApiRequest.mockRejectedValue(new Error("boom"));
    await expect(getAllAppSettings()).rejects.toThrow("boom");
  });
});

describe("getAppSetting", () => {
  it("requests app-settings/:id and returns the setting", async () => {
    const row = { id: "42", name: "A" };
    mockApiRequest.mockResolvedValue(row as never);
    const result = await getAppSetting("42");
    expect(mockApiRequest).toHaveBeenCalledWith("GET", "app-settings/42");
    expect(result).toEqual(row);
  });

  it("returns null when the response is falsy", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    expect(await getAppSetting("42")).toBeNull();
  });

  it("re-throws on error", async () => {
    mockApiRequest.mockRejectedValue(new Error("boom"));
    await expect(getAppSetting("42")).rejects.toThrow("boom");
  });
});

describe("createAppSetting", () => {
  it("POSTs the whitelisted fields and returns the created setting", async () => {
    const created = { id: "1", name: "A" };
    mockApiRequest.mockResolvedValue(created as never);
    const result = await createAppSetting({
      name: "A",
      type: "Security",
      values: { data_residency: ["eu"] },
      description: "desc",
      is_active: 1,
    } as never);
    expect(mockApiRequest).toHaveBeenCalledWith("POST", "app-settings", {
      name: "A",
      type: "Security",
      values: { data_residency: ["eu"] },
      description: "desc",
      is_active: 1,
    });
    expect(result).toEqual(created);
  });

  it("throws when the response is falsy", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    await expect(createAppSetting({ name: "A" } as never)).rejects.toThrow(
      "Failed to create app setting"
    );
  });
});

describe("updateAppSetting", () => {
  it("PATCHes only the provided fields", async () => {
    const updated = { id: "7", name: "B" };
    mockApiRequest.mockResolvedValue(updated as never);
    const result = await updateAppSetting("7", { name: "B", is_active: 0 } as never);
    expect(mockApiRequest).toHaveBeenCalledWith("PATCH", "app-settings/7", {
      name: "B",
      is_active: 0,
    });
    expect(result).toEqual(updated);
  });

  it("throws when the response is falsy", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    await expect(updateAppSetting("7", { name: "B" } as never)).rejects.toThrow(
      "Failed to update app setting"
    );
  });
});

describe("deleteAppSetting", () => {
  it("DELETEs app-settings/:id", async () => {
    mockApiRequest.mockResolvedValue(undefined as never);
    await deleteAppSetting("9");
    expect(mockApiRequest).toHaveBeenCalledWith("DELETE", "app-settings/9");
  });

  it("re-throws on error", async () => {
    mockApiRequest.mockRejectedValue(new Error("boom"));
    await expect(deleteAppSetting("9")).rejects.toThrow("boom");
  });
});

describe("testAppSettingConnection", () => {
  it("POSTs type + values and returns the result verbatim", async () => {
    const res = { success: true, message: "ok" };
    mockApiRequest.mockResolvedValue(res as never);
    const values = { host: "db" };
    const result = await testAppSettingConnection("Security" as never, values);
    expect(mockApiRequest).toHaveBeenCalledWith("POST", "app-settings/test-connection", {
      type: "Security",
      values,
    });
    expect(result).toEqual(res);
  });
});

describe("getAppSettingsFormSchemas", () => {
  it("GETs /app-settings/form_schemas and returns the schema", async () => {
    const schema = { fields: [] };
    mockApiRequest.mockResolvedValue(schema as never);
    const result = await getAppSettingsFormSchemas();
    expect(mockApiRequest).toHaveBeenCalledWith("GET", "/app-settings/form_schemas");
    expect(result).toEqual(schema);
  });

  it("re-throws on error", async () => {
    mockApiRequest.mockRejectedValue(new Error("boom"));
    await expect(getAppSettingsFormSchemas()).rejects.toThrow("boom");
  });
});

describe("getSecuritySettings", () => {
  it("prefers the active Security row", async () => {
    const active = { id: "2", type: "Security", is_active: 1 };
    mockApiRequest.mockResolvedValue([
      { id: "1", type: "Security", is_active: 0 },
      active,
    ] as never);
    expect(await getSecuritySettings()).toEqual(active);
  });

  it("falls back to any Security row when none is active", async () => {
    const inactive = { id: "1", type: "Security", is_active: 0 };
    mockApiRequest.mockResolvedValue([inactive] as never);
    expect(await getSecuritySettings()).toEqual(inactive);
  });

  it("returns null when there is no Security row", async () => {
    mockApiRequest.mockResolvedValue([{ id: "1", type: "Other", is_active: 1 }] as never);
    expect(await getSecuritySettings()).toBeNull();
  });

  it("returns null when the underlying request fails", async () => {
    mockApiRequest.mockRejectedValue(new Error("boom"));
    expect(await getSecuritySettings()).toBeNull();
  });
});

describe("updateSecuritySettings", () => {
  it("PATCHes when the settings have an id", async () => {
    mockApiRequest.mockResolvedValue({ id: "5" } as never);
    await updateSecuritySettings({
      id: "5",
      name: "Sec",
      type: "Security",
      values: { data_residency: ["eu"] },
      is_active: 1,
    });
    expect(mockApiRequest).toHaveBeenCalledWith("PATCH", "app-settings/5", {
      name: "Sec",
      type: "Security",
      values: { data_residency: ["eu"] },
      description: "Data residency and security policy settings",
      is_active: 1,
    });
  });

  it("POSTs with the default description when there is no id", async () => {
    mockApiRequest.mockResolvedValue({ id: "new" } as never);
    await updateSecuritySettings({
      name: "Sec",
      type: "Security",
      values: { data_residency: ["us"] },
      is_active: 1,
    });
    expect(mockApiRequest).toHaveBeenCalledWith("POST", "app-settings", {
      name: "Sec",
      type: "Security",
      values: { data_residency: ["us"] },
      description: "Data residency and security policy settings",
      is_active: 1,
    });
  });
});

describe("updateFileManagerSettings", () => {
  it("PATCHes and drops the id from the payload when an id is present", async () => {
    mockApiRequest.mockResolvedValue({ id: "3" } as never);
    await updateFileManagerSettings({
      id: "3",
      name: "FM",
      type: "FileManager",
      values: { provider: "s3" },
      is_active: 1,
    } as never);
    expect(mockApiRequest).toHaveBeenCalledWith("PATCH", "app-settings/3", {
      name: "FM",
      type: "FileManager",
      values: { provider: "s3" },
      description: "File manager settings for the application",
      is_active: 1,
    });
  });

  it("POSTs with the default description when there is no id", async () => {
    mockApiRequest.mockResolvedValue({ id: "new" } as never);
    await updateFileManagerSettings({
      name: "FM",
      type: "FileManager",
      values: { provider: "s3" },
      is_active: 1,
    } as never);
    expect(mockApiRequest).toHaveBeenCalledWith("POST", "app-settings", {
      name: "FM",
      type: "FileManager",
      values: { provider: "s3" },
      description: "File manager settings for the application",
      is_active: 1,
    });
  });
});
