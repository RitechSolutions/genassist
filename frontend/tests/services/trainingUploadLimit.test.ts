import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { AxiosError, AxiosHeaders } from "axios";

vi.mock("@/config/api", () => ({
  apiRequest: vi.fn(),
  getApiUrl: vi.fn(async () => "http://localhost/api/"),
  getApiUrlString: "http://localhost/api/",
  formatUploadOrNetworkError: (e: unknown) =>
    e instanceof AxiosError
      ? String((e.response?.data as { error_detail?: string })?.error_detail ?? e.message)
      : e instanceof Error
        ? e.message
        : String(e),
  API_DEFAULT_TIMEOUT_MS: 1000,
  API_UPLOAD_TIMEOUT_MS: 1000,
  api: { get: vi.fn(), post: vi.fn(), put: vi.fn(), patch: vi.fn(), delete: vi.fn(), request: vi.fn() },
}));

vi.mock("@/services/apiKeys", () => ({
  getApiKeys: vi.fn(),
  revealApiKey: vi.fn(),
}));

import { api } from "@/config/api";
import { getFileManagerCaps, uploadFiles } from "@/services/api";
import { formatBytes } from "@/helpers/formatters";
import { uploadSizeError } from "@/helpers/uploadSize";

const GIB = 1024 ** 3;
const LIMIT = 2 * GIB;
const mockGet = vi.mocked(api.get);
const mockPost = vi.mocked(api.post);

/** A File-like object of any size, without allocating its bytes. */
const fakeFile = (name: string, size: number) =>
  ({ name, size, type: "", slice: () => new Blob(["x"]) }) as unknown as File;

const grantPermissions = (permissions: string[]) =>
  vi.stubGlobal("localStorage", {
    getItem: (key: string) => (key === "permissions" ? JSON.stringify(permissions) : null),
  });

const tooLarge = () =>
  new AxiosError("Request failed with status code 413", "ERR_BAD_REQUEST", undefined, undefined, {
    status: 413,
    statusText: "Payload Too Large",
    headers: {},
    config: { headers: new AxiosHeaders() },
    data: {
      error_key: "ML_TRAINING_UPLOAD_TOO_LARGE",
      error_detail: "This file is 2 GB, which is larger than the maximum training data upload size of 2 GB.",
    },
  });

beforeEach(() => vi.clearAllMocks());
afterEach(() => vi.unstubAllGlobals());

describe("formatBytes", () => {
  it.each([
    [LIMIT, "2 GB"],
    [2.5 * GIB, "2.5 GB"],
    [300 * 1024 ** 2, "300 MB"],
    [512, "512 bytes"],
  ])("formats %d as %s", (size, label) => {
    expect(formatBytes(size)).toBe(label);
  });
});

describe("uploadSizeError (checked before uploading)", () => {
  it("allows a file below the limit", () => {
    expect(uploadSizeError({ name: "a.csv", size: LIMIT - 1 }, LIMIT, "2 GB")).toBeNull();
  });

  it("allows a file exactly at the limit", () => {
    expect(uploadSizeError({ name: "a.csv", size: LIMIT }, LIMIT, "2 GB")).toBeNull();
  });

  it("rejects a file above the limit with both sizes in the message", () => {
    expect(uploadSizeError({ name: "big.parquet", size: 2.5 * GIB }, LIMIT, "2 GB")).toBe(
      "big.parquet is 2.5 GB, which is larger than the maximum upload size of 2 GB.",
    );
  });

  it("allows any size when no limit is known", () => {
    expect(uploadSizeError({ name: "a.csv", size: 10 * GIB })).toBeNull();
  });
});

describe("uploadFiles with purpose training_data", () => {
  it("sends the purpose on a small single-request upload", async () => {
    grantPermissions([]);
    await getFileManagerCaps(true);
    mockPost.mockResolvedValue({ data: [{ file_id: "f1" }] } as never);

    await uploadFiles([fakeFile("small.csv", 1024)], { purpose: "training_data" });

    expect(mockPost.mock.calls[0][0]).toBe(
      "http://localhost/api/file-manager/upload?purpose=training_data",
    );
  });

  it("sends the purpose when starting a chunked upload of a file at the limit", async () => {
    grantPermissions([]);
    await getFileManagerCaps(true);
    mockPost.mockImplementation(async (url: string) => {
      if (url.endsWith("/upload-session")) return { data: { session_id: "s1", max_chunk_bytes: LIMIT } } as never;
      if (url.endsWith("/complete")) return { data: { file_id: "f1" } } as never;
      return { data: {} } as never;
    });

    await uploadFiles([fakeFile("big.parquet", LIMIT)], { purpose: "training_data" });

    const [url, body] = mockPost.mock.calls[0];
    expect(url).toBe("http://localhost/api/file-manager/upload-session");
    expect(body).toMatchObject({ expected_size: LIMIT, purpose: "training_data" });
  });

  it("shows the server's message when a chunked upload is over the limit", async () => {
    grantPermissions([]);
    await getFileManagerCaps(true);
    mockPost.mockRejectedValue(tooLarge());

    await expect(
      uploadFiles([fakeFile("big.parquet", LIMIT + 1)], { purpose: "training_data" }),
    ).rejects.toThrow("larger than the maximum training data upload size of 2 GB");
  });

  it("sends the purpose on a direct S3 presign and does not retry a rejected file", async () => {
    grantPermissions(["read:file"]);
    mockGet.mockResolvedValue({ data: { is_active: 1, values: { direct_s3_upload_enabled: true } } } as never);
    await getFileManagerCaps(true);
    mockPost.mockRejectedValue(tooLarge());

    await expect(
      uploadFiles([fakeFile("big.parquet", LIMIT + 1)], { purpose: "training_data" }),
    ).rejects.toThrow("larger than the maximum training data upload size of 2 GB");

    // Only the presign call: no fallback to the chunked upload for a refused file.
    expect(mockPost).toHaveBeenCalledTimes(1);
    const [url, body] = mockPost.mock.calls[0];
    expect(url).toBe("http://localhost/api/file-manager/upload-session/presign");
    expect(body).toMatchObject({ expected_size: LIMIT + 1, purpose: "training_data" });
  });

  it("falls back to the chunked upload when the direct S3 upload fails with another 400", async () => {
    grantPermissions(["read:file"]);
    mockGet.mockResolvedValue({ data: { is_active: 1, values: { direct_s3_upload_enabled: true } } } as never);
    await getFileManagerCaps(true);
    const sessionNotFound = new AxiosError("Request failed with status code 400", "ERR_BAD_REQUEST", undefined, undefined, {
      status: 400,
      statusText: "Bad Request",
      headers: {},
      config: { headers: new AxiosHeaders() },
      data: { error_key: "MISSING_PARAMETER", error_detail: "Upload session not found." },
    });
    mockPost.mockRejectedValueOnce(sessionNotFound).mockRejectedValueOnce(new Error("chunked upload reached"));

    await expect(
      uploadFiles([fakeFile("data.parquet", 10)], { purpose: "training_data" }),
    ).rejects.toThrow("chunked upload reached");

    expect(mockPost).toHaveBeenCalledTimes(2);
    expect(mockPost.mock.calls[1][0]).toBe("http://localhost/api/file-manager/upload-session");
  });
});
