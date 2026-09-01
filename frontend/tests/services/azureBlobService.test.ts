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
  listBlobs,
  blobExists,
  uploadFile,
  uploadContent,
  deleteBlob,
  moveBlob,
  bucketExists,
} from "@/services/azureBlobService";

const mockApiRequest = vi.mocked(apiRequest);
beforeEach(() => vi.clearAllMocks());

const conn = { connection_string: "cs", container: "media" };

/** The FormData the service handed to apiRequest for the Nth call. */
const formDataArg = (call = 0) =>
  mockApiRequest.mock.calls[call][2] as unknown as FormData;

describe("listBlobs", () => {
  it("POSTs azure-blob-storage/list with the params and returns the array", async () => {
    const blobs = ["a.txt", "b.txt"];
    mockApiRequest.mockResolvedValue(blobs as never);
    const params = { ...conn, prefix: "inbox/" };
    const result = await listBlobs(params);
    expect(mockApiRequest).toHaveBeenCalledWith("POST", "azure-blob-storage/list", params);
    expect(result).toEqual(blobs);
  });

  it("returns [] when the response is null", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    expect(await listBlobs(conn)).toEqual([]);
  });
});

describe("blobExists", () => {
  it("POSTs azure-blob-storage/exists and unwraps `exists`", async () => {
    mockApiRequest.mockResolvedValue({ exists: true } as never);
    const params = { ...conn, filename: "a.txt", prefix: "inbox/" };
    expect(await blobExists(params)).toBe(true);
    expect(mockApiRequest).toHaveBeenCalledWith("POST", "azure-blob-storage/exists", params);
  });

  it("returns false when `exists` is false", async () => {
    mockApiRequest.mockResolvedValue({ exists: false } as never);
    expect(await blobExists({ ...conn, filename: "a.txt" })).toBe(false);
  });

  it("returns false when the response is null", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    expect(await blobExists({ ...conn, filename: "a.txt" })).toBe(false);
  });
});

describe("uploadFile", () => {
  const file = new File(["hello"], "a.txt", { type: "text/plain" });

  it("POSTs azure-blob-storage/upload with a FormData body and returns the url", async () => {
    mockApiRequest.mockResolvedValue({ url: "https://blob/a.txt" } as never);
    const result = await uploadFile({ ...conn, file, destination_name: "a.txt", prefix: "inbox/" });

    expect(result).toBe("https://blob/a.txt");
    const [method, endpoint] = mockApiRequest.mock.calls[0];
    expect(method).toBe("POST");
    expect(endpoint).toBe("azure-blob-storage/upload");

    const fd = formDataArg();
    expect(fd).toBeInstanceOf(FormData);
    expect(fd.get("file")).toBe(file);
    expect(fd.get("connection_string")).toBe("cs");
    expect(fd.get("container")).toBe("media");
    expect(fd.get("destination_name")).toBe("a.txt");
    expect(fd.get("prefix")).toBe("inbox/");
  });

  it("defaults a missing connection_string/container to empty strings", async () => {
    mockApiRequest.mockResolvedValue({ url: "https://blob/a.txt" } as never);
    await uploadFile({ file, destination_name: "a.txt" });

    const fd = formDataArg();
    expect(fd.get("connection_string")).toBe("");
    expect(fd.get("container")).toBe("");
  });

  it("omits `prefix` entirely when it is not provided", async () => {
    mockApiRequest.mockResolvedValue({ url: "https://blob/a.txt" } as never);
    await uploadFile({ ...conn, file, destination_name: "a.txt" });
    expect(formDataArg().has("prefix")).toBe(false);
  });

  it("keeps an explicit empty-string prefix", async () => {
    mockApiRequest.mockResolvedValue({ url: "https://blob/a.txt" } as never);
    await uploadFile({ ...conn, file, destination_name: "a.txt", prefix: "" });
    expect(formDataArg().get("prefix")).toBe("");
  });

  it("throws when the response carries no url", async () => {
    mockApiRequest.mockResolvedValue({} as never);
    await expect(uploadFile({ ...conn, file, destination_name: "a.txt" })).rejects.toThrow(
      "Upload failed."
    );
  });

  it("throws when the response is null", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    await expect(uploadFile({ ...conn, file, destination_name: "a.txt" })).rejects.toThrow(
      "Upload failed."
    );
  });
});

describe("uploadContent", () => {
  it("POSTs the (differently prefixed) azureblob/upload-content endpoint and returns the url", async () => {
    mockApiRequest.mockResolvedValue({ url: "https://blob/note.txt" } as never);
    const payload = { ...conn, filename: "note.txt", content: "hi", binary: false };
    expect(await uploadContent(payload)).toBe("https://blob/note.txt");
    expect(mockApiRequest).toHaveBeenCalledWith("POST", "azureblob/upload-content", payload);
  });

  it("throws when the response carries no url", async () => {
    mockApiRequest.mockResolvedValue({} as never);
    await expect(uploadContent({ ...conn, filename: "note.txt" })).rejects.toThrow(
      "Upload-content failed."
    );
  });
});

describe("deleteBlob", () => {
  it("DELETEs azure-blob-storage/file with the payload", async () => {
    mockApiRequest.mockResolvedValue({ deleted: true } as never);
    const payload = { ...conn, filename: "a.txt", prefix: "inbox/" };
    await expect(deleteBlob(payload)).resolves.toBeUndefined();
    expect(mockApiRequest).toHaveBeenCalledWith("DELETE", "azure-blob-storage/file", payload);
  });

  it("throws when the response is falsy", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    await expect(deleteBlob({ ...conn, filename: "a.txt" })).rejects.toThrow(
      "Failed to delete Azure blob"
    );
  });
});

describe("moveBlob", () => {
  it("POSTs azure-blob-storage/move and returns the new url", async () => {
    mockApiRequest.mockResolvedValue({ url: "https://blob/done/a.txt" } as never);
    const payload = {
      ...conn,
      source_name: "a.txt",
      destination_name: "a.txt",
      source_prefix: "inbox/",
      destination_prefix: "done/",
    };
    expect(await moveBlob(payload)).toBe("https://blob/done/a.txt");
    expect(mockApiRequest).toHaveBeenCalledWith("POST", "azure-blob-storage/move", payload);
  });

  it("throws when the response carries no url", async () => {
    mockApiRequest.mockResolvedValue({} as never);
    await expect(
      moveBlob({ ...conn, source_name: "a.txt", destination_name: "b.txt" })
    ).rejects.toThrow("Move failed.");
  });
});

describe("bucketExists", () => {
  it("POSTs azure-blob-storage/bucket-exists and unwraps `exists`", async () => {
    mockApiRequest.mockResolvedValue({ exists: true } as never);
    expect(await bucketExists(conn)).toBe(true);
    expect(mockApiRequest).toHaveBeenCalledWith("POST", "azure-blob-storage/bucket-exists", conn);
  });

  it("returns false when the response is null", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    expect(await bucketExists(conn)).toBe(false);
  });
});
