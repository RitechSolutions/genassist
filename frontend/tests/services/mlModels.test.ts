import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("@/config/api", () => ({
  apiRequest: vi.fn(),
  getApiUrl: vi.fn(async () => "http://localhost/api/"),
  getApiUrlString: "http://localhost/api/",
  formatUploadOrNetworkError: (e: unknown) => (e instanceof Error ? e.message : String(e)),
  API_DEFAULT_TIMEOUT_MS: 1000,
  API_UPLOAD_TIMEOUT_MS: 1000,
  API_PREPROCESSING_TIMEOUT_MS: 5000,
  api: { get: vi.fn(), post: vi.fn(), put: vi.fn(), patch: vi.fn(), delete: vi.fn(), request: vi.fn() },
}));

import { apiRequest, API_PREPROCESSING_TIMEOUT_MS } from "@/config/api";
import {
  getAllMLModels,
  getMLModel,
  createMLModel,
  updateMLModel,
  deleteMLModel,
  analyzeCSV,
} from "@/services/mlModels";

const mockApiRequest = vi.mocked(apiRequest);

beforeEach(() => {
  vi.clearAllMocks();
  vi.spyOn(console, "error").mockImplementation(() => {});
});

describe("getAllMLModels", () => {
  it("returns the models array", async () => {
    const models = [{ id: "m1" }];
    mockApiRequest.mockResolvedValue(models as never);
    expect(await getAllMLModels()).toBe(models);
    expect(mockApiRequest).toHaveBeenCalledWith("GET", "ml-models");
  });

  it("falls back to [] when the response is nullish", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    expect(await getAllMLModels()).toEqual([]);
  });
});

describe("getMLModel", () => {
  it("returns the model", async () => {
    const model = { id: "m1" };
    mockApiRequest.mockResolvedValue(model as never);
    expect(await getMLModel("m1")).toBe(model);
    expect(mockApiRequest).toHaveBeenCalledWith("GET", "ml-models/m1");
  });

  it("falls back to null when the response is nullish", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    expect(await getMLModel("m1")).toBeNull();
  });
});

describe("createMLModel", () => {
  it("posts the model data and returns the created model", async () => {
    const modelData = { name: "x" } as never;
    const created = { id: "m1" };
    mockApiRequest.mockResolvedValue(created as never);
    expect(await createMLModel(modelData)).toBe(created);
    expect(mockApiRequest).toHaveBeenCalledWith("POST", "ml-models", modelData);
  });

  it("rethrows when apiRequest rejects", async () => {
    mockApiRequest.mockRejectedValue(new Error("boom"));
    await expect(createMLModel({} as never)).rejects.toThrow("boom");
  });
});

describe("updateMLModel", () => {
  it("puts the model data and returns the updated model", async () => {
    const modelData = { name: "x" } as never;
    const updated = { id: "m1" };
    mockApiRequest.mockResolvedValue(updated as never);
    expect(await updateMLModel("m1", modelData)).toBe(updated);
    expect(mockApiRequest).toHaveBeenCalledWith("PUT", "ml-models/m1", modelData);
  });

  it("rethrows when apiRequest rejects", async () => {
    mockApiRequest.mockRejectedValue(new Error("boom"));
    await expect(updateMLModel("m1", {})).rejects.toThrow("boom");
  });
});

describe("deleteMLModel", () => {
  it("deletes the model", async () => {
    mockApiRequest.mockResolvedValue(undefined as never);
    await deleteMLModel("m1");
    expect(mockApiRequest).toHaveBeenCalledWith("DELETE", "ml-models/m1");
  });

  it("rethrows when apiRequest rejects", async () => {
    mockApiRequest.mockRejectedValue(new Error("boom"));
    await expect(deleteMLModel("m1")).rejects.toThrow("boom");
  });
});

describe("analyzeCSV", () => {
  it("posts only file_url when no python code is provided", async () => {
    const result = { row_count: 1 };
    mockApiRequest.mockResolvedValue(result as never);
    expect(await analyzeCSV("http://x/file.csv")).toBe(result);
    expect(mockApiRequest).toHaveBeenCalledWith(
      "POST",
      "ml-models/analyze-csv",
      { file_url: "http://x/file.csv" },
      { timeout: API_PREPROCESSING_TIMEOUT_MS },
    );
  });

  it("includes python_code when provided", async () => {
    mockApiRequest.mockResolvedValue({ row_count: 1 } as never);
    await analyzeCSV("http://x/file.csv", "df.head()");
    expect(mockApiRequest).toHaveBeenCalledWith(
      "POST",
      "ml-models/analyze-csv",
      { file_url: "http://x/file.csv", python_code: "df.head()" },
      { timeout: API_PREPROCESSING_TIMEOUT_MS },
    );
  });

  it("throws when the response is falsy", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    await expect(analyzeCSV("http://x/file.csv")).rejects.toThrow("Failed to analyze CSV");
  });

  it("rethrows when apiRequest rejects", async () => {
    mockApiRequest.mockRejectedValue(new Error("boom"));
    await expect(analyzeCSV("http://x/file.csv")).rejects.toThrow("boom");
  });
});
