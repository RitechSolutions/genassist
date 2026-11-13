import { describe, it, expect, vi, beforeEach } from "vitest";

// The real config/api is loaded below for its upload error formatter; it reads the API
// URL when it loads, so stub it first (CI has no .env).
vi.hoisted(() => {
  vi.stubEnv("VITE_PUBLIC_API_URL", "http://localhost/api/");
});

// The real upload error formatter, so the messages users see are what is tested.
vi.mock("@/config/api", async (importOriginal) => ({
  formatUploadOrNetworkError: (await importOriginal<typeof import("@/config/api")>()).formatUploadOrNetworkError,
  apiRequest: vi.fn(),
  getApiUrl: vi.fn(async () => "http://localhost/api/"),
  getApiUrlString: "http://localhost/api/",
  API_DEFAULT_TIMEOUT_MS: 1000,
  API_UPLOAD_TIMEOUT_MS: 1000,
  API_PREPROCESSING_TIMEOUT_MS: 5000,
  api: { get: vi.fn(), post: vi.fn(), put: vi.fn(), patch: vi.fn(), delete: vi.fn(), request: vi.fn() },
}));

import { AxiosError, CanceledError } from "axios";
import { api, apiRequest, API_PREPROCESSING_TIMEOUT_MS } from "@/config/api";
import {
  getAllMLModels,
  getMLModel,
  createMLModel,
  updateMLModel,
  deleteMLModel,
  analyzeCSV,
  analyzeTrainingFile,
  previewQuery,
  profileData,
  discardTrainingUpload,
  uploadModelFile,
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

  it("includes File Manager identity for non-local CSV files", async () => {
    mockApiRequest.mockResolvedValue({ row_count: 1 } as never);
    await analyzeCSV(
      "https://app.example/api/file-manager/files/file-1/source",
      undefined,
      { id: "file-1", name: "training.csv" },
    );
    expect(mockApiRequest).toHaveBeenCalledWith(
      "POST",
      "ml-models/analyze-csv",
      {
        file_url: "https://app.example/api/file-manager/files/file-1/source",
        file_id: "file-1",
        file_name: "training.csv",
      },
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

  it("surfaces the safe backend detail when file preview fails", async () => {
    mockApiRequest.mockRejectedValue({
      message: "Request failed with status code 400",
      response: { data: { detail: "The CSV file could not be decoded as UTF-8." } },
    });

    await expect(analyzeCSV("http://x/file.csv")).rejects.toThrow(
      "The CSV file could not be decoded as UTF-8.",
    );
  });
});

describe("analyzeTrainingFile", () => {
  it("previews a training file", async () => {
    const result = { row_count: 1, column_count: 1, column_names: ["id"], sample_data: [{ id: 1 }], columns_info: [] };
    mockApiRequest.mockResolvedValue(result as never);

    await expect(analyzeTrainingFile({ file_id: "f1", file_name: "data.csv" })).resolves.toBe(result);
    expect(mockApiRequest).toHaveBeenCalledWith(
      "POST",
      "ml-models/analyze-file",
      { file_id: "f1", file_name: "data.csv" },
      { timeout: API_PREPROCESSING_TIMEOUT_MS },
    );
  });

  it("surfaces the backend detail, e.g. a repeated column name", async () => {
    const detail = "The CSV file has two columns named 'id'. Give every column a unique name and upload the file again.";
    mockApiRequest.mockRejectedValue({
      message: "Request failed with status code 400",
      response: { data: { detail } },
    });

    await expect(analyzeTrainingFile({ file_id: "f1", file_name: "data.csv" })).rejects.toThrow(detail);
  });

  it("uses a clear fallback when the backend provides no detail", async () => {
    mockApiRequest.mockRejectedValue(new Error("Request failed with status code 500"));

    await expect(analyzeTrainingFile({ file_id: "f1", file_name: "data.csv" })).rejects.toThrow(
      "The file preview could not be generated. Please try again.",
    );
  });
});

describe("previewQuery", () => {
  it("requests a bounded SQL query preview", async () => {
    const result = {
      row_count: 1,
      column_count: 1,
      column_names: ["id"],
      sample_data: [{ id: 1 }],
      columns_info: [],
    };
    mockApiRequest.mockResolvedValue(result as never);

    await expect(
      previewQuery({
        data_source_id: "datasource-1",
        query: "SELECT id FROM users",
      }),
    ).resolves.toBe(result);
    expect(mockApiRequest).toHaveBeenCalledWith(
      "POST",
      "ml-models/preview-query",
      {
        data_source_id: "datasource-1",
        query: "SELECT id FROM users",
      },
      { timeout: API_PREPROCESSING_TIMEOUT_MS },
    );
  });

  it("throws when the preview response is empty", async () => {
    mockApiRequest.mockResolvedValue(null as never);

    await expect(
      previewQuery({
        data_source_id: "datasource-1",
        query: "SELECT id FROM users",
      }),
    ).rejects.toThrow("Failed to preview query");
  });

  it("surfaces the safe backend detail when query preview fails", async () => {
    mockApiRequest.mockRejectedValue({
      message: "Request failed with status code 400",
      response: { data: { detail: "Database query failed: column \"name\" does not exist" } },
    });

    await expect(
      previewQuery({
        data_source_id: "datasource-1",
        query: "SELECT name FROM users",
      }),
    ).rejects.toThrow('Database query failed: column "name" does not exist');
  });

  it("uses a clear fallback when the backend provides no safe detail", async () => {
    mockApiRequest.mockRejectedValue(
      new Error("Request failed with status code 500"),
    );

    await expect(
      previewQuery({
        data_source_id: "datasource-1",
        query: "SELECT id FROM users",
      }),
    ).rejects.toThrow("The query preview could not be generated. Please try again.");
  });
});

describe("profileData", () => {
  beforeEach(() => {
    vi.stubGlobal("URL", {
      createObjectURL: vi.fn(() => "blob:profile"),
      revokeObjectURL: vi.fn(),
    });
  });

  it("profiles a CSV by File Manager ID", async () => {
    const click = vi.fn();
    vi.stubGlobal("document", {
      createElement: vi.fn(() => ({ click })),
    });
    mockApiRequest.mockResolvedValue(new Blob(["report"]) as never);

    await profileData(
      {
        source_type: "csv",
        file_id: "file-1",
        file_name: "training.csv",
      },
      "training_profile.html",
    );

    expect(mockApiRequest).toHaveBeenCalledWith(
      "POST",
      "ml-models/profile-data",
      {
        source_type: "csv",
        file_id: "file-1",
        file_name: "training.csv",
      },
      {
        timeout: API_PREPROCESSING_TIMEOUT_MS,
        responseType: "blob",
      },
    );
    expect(click).toHaveBeenCalledOnce();
    expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:profile");
  });

  it("profiles a SQL query result", async () => {
    vi.stubGlobal("document", {
      createElement: vi.fn(() => ({ click: vi.fn() })),
    });
    mockApiRequest.mockResolvedValue(new Blob(["report"]) as never);

    await profileData(
      {
        source_type: "datasource",
        data_source_id: "datasource-1",
        query: "SELECT * FROM training_data",
      },
      "query_profile.html",
    );

    expect(mockApiRequest).toHaveBeenCalledWith(
      "POST",
      "ml-models/profile-data",
      {
        source_type: "datasource",
        data_source_id: "datasource-1",
        query: "SELECT * FROM training_data",
      },
      {
        timeout: API_PREPROCESSING_TIMEOUT_MS,
        responseType: "blob",
      },
    );
  });

  it("throws when the profile response is empty", async () => {
    mockApiRequest.mockResolvedValue(null as never);

    await expect(
      profileData(
        { source_type: "csv", file_id: "file-1" },
        "data_profile.html",
      ),
    ).rejects.toThrow("Failed to generate data profile");
  });

  it("decodes a safe backend detail from a failed profile blob", async () => {
    mockApiRequest.mockRejectedValue({
      message: "Request failed with status code 400",
      response: {
        data: new Blob([
          JSON.stringify({ detail: "The query returned no rows." }),
        ], { type: "application/json" }),
      },
    });

    await expect(
      profileData(
        {
          source_type: "datasource",
          data_source_id: "datasource-1",
          query: "SELECT * FROM users WHERE 1 = 0",
        },
        "query_profile.html",
      ),
    ).rejects.toThrow("The query returned no rows.");
  });
});

describe("discardTrainingUpload", () => {
  it("asks the server to remove the unused training upload", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    await discardTrainingUpload("f/1");
    expect(mockApiRequest).toHaveBeenCalledWith("DELETE", "ml-models/training-data/upload/f%2F1");
  });

  it("only logs a failure, so it never hides the dialog's own error", async () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    mockApiRequest.mockRejectedValue(new Error("404"));
    await expect(discardTrainingUpload("f1")).resolves.toBeUndefined();
    expect(warn).toHaveBeenCalled();
  });
});

describe("uploadModelFile", () => {
  // Built per test: Node below 20 has no global File, and a describe body runs at collection.
  let file: File;
  beforeEach(() => {
    file = new File([new Uint8Array(2000)], "model.pkl", { type: "application/octet-stream" });
  });
  const uploaded = { file_id: "f1", file_path: null, original_filename: "model.pkl" };
  const mockPost = vi.mocked(api.post);

  it("posts the file through the shared API client, which renews the login", async () => {
    mockPost.mockResolvedValue({ data: uploaded } as never);
    expect(await uploadModelFile(file)).toBe(uploaded);
    const [url, body, config] = mockPost.mock.calls[0];
    expect(url).toBe("http://localhost/api/ml-models/upload");
    expect(body).toBeInstanceOf(FormData);
    expect((body as FormData).get("file")).toBe(file);
    expect(config).toMatchObject({ timeout: 1000 });
    // Not through apiRequest, whose server-status handling would mark the app down on a proxy timeout
    expect(mockApiRequest).not.toHaveBeenCalled();
  });

  it("reports progress in percent, using the file size when the total is unknown", async () => {
    mockPost.mockResolvedValue({ data: uploaded } as never);
    const progress: number[] = [];
    await uploadModelFile(file, (p) => progress.push(p));
    const { onUploadProgress } = mockPost.mock.calls[0][2] as {
      onUploadProgress: (e: { loaded: number; total?: number }) => void;
    };
    onUploadProgress({ loaded: 500, total: 1000 });
    onUploadProgress({ loaded: 1000 });
    onUploadProgress({ loaded: 2000, total: 2000 });
    expect(progress).toEqual([50, 50, 100]);
  });

  it("fails with a message when the server returns nothing", async () => {
    mockPost.mockResolvedValue({ data: null } as never);
    await expect(uploadModelFile(file)).rejects.toThrow("The model file could not be uploaded.");
  });

  it("turns a proxy's HTML error page into a plain message", async () => {
    const proxy413 = new AxiosError("Request failed with status code 413", "ERR_BAD_REQUEST", undefined, undefined, {
      status: 413,
      data: "<html><head><title>413 Request Entity Too Large</title></head></html>",
    } as never);
    mockPost.mockRejectedValue(proxy413);
    await expect(uploadModelFile(file)).rejects.toThrow(/^File is too large for the server/);
  });

  it("explains a gateway timeout in plain words", async () => {
    const gateway504 = new AxiosError("Request failed with status code 504", "ERR_BAD_RESPONSE", undefined, undefined, {
      status: 504,
      data: "<html><body>504 Gateway Time-out</body></html>",
    } as never);
    mockPost.mockRejectedValue(gateway504);
    await expect(uploadModelFile(file)).rejects.toThrow(
      "The server took too long to accept the model file. Try again; if it keeps happening, ask an admin to check the upload time limit.",
    );
  });

  it("passes the server's own message on", async () => {
    const refused = new AxiosError("Request failed with status code 400", "ERR_BAD_REQUEST", undefined, undefined, {
      status: 400,
      data: { error_detail: "Only .pkl files are allowed." },
    } as never);
    mockPost.mockRejectedValue(refused);
    await expect(uploadModelFile(file)).rejects.toThrow("Only .pkl files are allowed.");
  });

  it("rethrows a cancelled request as it is, so the form shows no error", async () => {
    const cancelled = new CanceledError("Session ended");
    mockPost.mockRejectedValue(cancelled);
    await expect(uploadModelFile(file)).rejects.toBe(cancelled);
  });
});
