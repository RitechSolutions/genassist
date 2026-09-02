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

vi.mock("@/services/appSettings", () => ({
  getAllAppSettings: vi.fn(),
}));

import { apiRequest } from "@/config/api";
import { getAllAppSettings } from "@/services/appSettings";
import {
  getAllDataSources,
  getDataSource,
  createDataSource,
  updateDataSource,
  deleteDataSource,
  getDataSourceFormSchemas,
  testDataSourceConnection,
  createTempGmailDataSource,
  createTempOffice365DataSource,
  getGmailClientId,
  getOffice365SettingValue,
} from "@/services/dataSources";
import type { DataSource } from "@/interfaces/dataSource.interface";

const mockApiRequest = vi.mocked(apiRequest);
const mockGetAllAppSettings = vi.mocked(getAllAppSettings);

// Keep expected-error console noise out of the test output.
vi.spyOn(console, "error").mockImplementation(() => {});

beforeEach(() => vi.clearAllMocks());

describe("getAllDataSources", () => {
  it("GETs datasources/ and returns the list", async () => {
    const list = [{ id: "1" }, { id: "2" }];
    mockApiRequest.mockResolvedValue(list as never);

    const result = await getAllDataSources();

    expect(mockApiRequest).toHaveBeenCalledWith("GET", "datasources/");
    expect(result).toEqual(list);
  });

  it("rethrows on error", async () => {
    mockApiRequest.mockRejectedValue(new Error("boom"));
    await expect(getAllDataSources()).rejects.toThrow("boom");
  });
});

describe("getDataSource", () => {
  it("GETs datasources/:id and returns it", async () => {
    const ds = { id: "abc" };
    mockApiRequest.mockResolvedValue(ds as never);

    const result = await getDataSource("abc");

    expect(mockApiRequest).toHaveBeenCalledWith("GET", "datasources/abc");
    expect(result).toEqual(ds);
  });

  it("rethrows on error", async () => {
    mockApiRequest.mockRejectedValue(new Error("nope"));
    await expect(getDataSource("abc")).rejects.toThrow("nope");
  });
});

describe("createDataSource", () => {
  it("POSTs a deep-cloned payload and returns the response", async () => {
    const data = { name: "src", source_type: "gmail" } as unknown as DataSource;
    const created = { id: "new", name: "src" };
    mockApiRequest.mockResolvedValue(created as never);

    const result = await createDataSource(data);

    expect(mockApiRequest).toHaveBeenCalledWith(
      "POST",
      "datasources/",
      { name: "src", source_type: "gmail" },
    );
    expect(result).toEqual(created);
  });

  it("rethrows on error", async () => {
    mockApiRequest.mockRejectedValue(new Error("create-fail"));
    await expect(createDataSource({} as DataSource)).rejects.toThrow("create-fail");
  });
});

describe("updateDataSource", () => {
  it("PUTs a deep-cloned payload to datasources/:id", async () => {
    const patch = { name: "renamed" };
    const updated = { id: "u1", name: "renamed" };
    mockApiRequest.mockResolvedValue(updated as never);

    const result = await updateDataSource("u1", patch);

    expect(mockApiRequest).toHaveBeenCalledWith("PUT", "datasources/u1", { name: "renamed" });
    expect(result).toEqual(updated);
  });

  it("rethrows on error", async () => {
    mockApiRequest.mockRejectedValue(new Error("update-fail"));
    await expect(updateDataSource("u1", {})).rejects.toThrow("update-fail");
  });
});

describe("deleteDataSource", () => {
  it("DELETEs datasources/:id and resolves void", async () => {
    mockApiRequest.mockResolvedValue(undefined as never);

    await expect(deleteDataSource("d1")).resolves.toBeUndefined();
    expect(mockApiRequest).toHaveBeenCalledWith("DELETE", "datasources/d1");
  });

  it("rethrows on error", async () => {
    mockApiRequest.mockRejectedValue(new Error("delete-fail"));
    await expect(deleteDataSource("d1")).rejects.toThrow("delete-fail");
  });
});

describe("getDataSourceFormSchemas", () => {
  it("GETs /datasources/form_schemas", async () => {
    const schema = { fields: [] };
    mockApiRequest.mockResolvedValue(schema as never);

    const result = await getDataSourceFormSchemas();

    expect(mockApiRequest).toHaveBeenCalledWith("GET", "/datasources/form_schemas");
    expect(result).toEqual(schema);
  });
});

describe("testDataSourceConnection", () => {
  it("POSTs to test-connection with no query when datasource_id is absent", async () => {
    const payload = { success: true, message: "ok" };
    mockApiRequest.mockResolvedValue(payload as never);

    const result = await testDataSourceConnection("gmail", { host: "h" });

    expect(mockApiRequest).toHaveBeenCalledWith("POST", "datasources/test-connection", {
      source_type: "gmail",
      connection_data: { host: "h" },
    });
    expect(result).toEqual(payload);
  });

  it("appends datasource_id query when provided", async () => {
    mockApiRequest.mockResolvedValue({ success: true, message: "ok" } as never);

    await testDataSourceConnection("o365", { host: "h" }, "ds1");

    expect(mockApiRequest).toHaveBeenCalledWith(
      "POST",
      "datasources/test-connection?datasource_id=ds1",
      { source_type: "o365", connection_data: { host: "h" } },
    );
  });
});

describe("createTempGmailDataSource", () => {
  it("creates a pending gmail datasource and returns its id", async () => {
    mockApiRequest.mockResolvedValue({ id: "gid" } as never);

    const result = await createTempGmailDataSource("My Gmail", "app1");

    expect(mockApiRequest).toHaveBeenCalledWith("POST", "datasources/", {
      name: "My Gmail",
      source_type: "gmail",
      connection_data: { app_settings_id: "app1" },
      is_active: 0,
      oauth_status: "pending",
    });
    expect(result).toBe("gid");
  });
});

describe("createTempOffice365DataSource", () => {
  it("creates a pending o365 datasource and returns its id", async () => {
    mockApiRequest.mockResolvedValue({ id: "oid" } as never);

    const result = await createTempOffice365DataSource("My O365", "app2");

    expect(mockApiRequest).toHaveBeenCalledWith("POST", "datasources/", {
      name: "My O365",
      source_type: "o365",
      connection_data: { app_settings_id: "app2" },
      is_active: 0,
      oauth_status: "pending",
    });
    expect(result).toBe("oid");
  });
});

describe("getGmailClientId", () => {
  it("returns the client id from the active Gmail app setting", async () => {
    mockGetAllAppSettings.mockResolvedValue([
      { type: "Gmail", is_active: 1, values: { gmail_client_id: "cid-123" } },
    ] as never);

    await expect(getGmailClientId()).resolves.toBe("cid-123");
  });

  it("throws when no active Gmail setting has a client id", async () => {
    mockGetAllAppSettings.mockResolvedValue([] as never);

    await expect(getGmailClientId()).rejects.toThrow("Gmail client ID not found in app settings");
  });
});

describe("getOffice365SettingValue", () => {
  it("returns the requested key from the active Microsoft app setting", async () => {
    mockGetAllAppSettings.mockResolvedValue([
      { type: "Microsoft", is_active: 1, values: { client_id: "mcid" } },
    ] as never);

    await expect(getOffice365SettingValue("client_id")).resolves.toBe("mcid");
  });

  it("throws when the key is missing", async () => {
    mockGetAllAppSettings.mockResolvedValue([
      { type: "Microsoft", is_active: 1, values: {} },
    ] as never);

    await expect(getOffice365SettingValue("client_id")).rejects.toThrow(
      "Microsoft client_id not found in app settings",
    );
  });
});
