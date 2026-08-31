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

import { api } from "@/config/api";
import { uploadAudio } from "@/services/audioUpload";

const mockPost = vi.mocked(api.post);
beforeEach(() => vi.clearAllMocks());

const file = new File(["audio-bytes"], "call.wav", { type: "audio/wav" });

const analysis = {
  id: "analysis-1",
  conversation_id: "conv-9",
  llm_analyst_id: "llm-1",
  tone: "neutral",
  topic: "billing",
  summary: "A billing question.",
};

/** The FormData the service handed to api.post. */
const formDataArg = () => mockPost.mock.calls[0][1] as unknown as FormData;

/** An axios-shaped error with a server response attached. */
const responseError = (status: number, data: unknown) =>
  Object.assign(new Error("Request failed"), { response: { status, data } });

describe("uploadAudio", () => {
  it("POSTs the absolute analyze_recording url with multipart headers", async () => {
    mockPost.mockResolvedValue({ data: analysis } as never);
    await uploadAudio(file, "agent-7");

    const [url, , config] = mockPost.mock.calls[0];
    expect(url).toBe("http://localhost/api/audio/analyze_recording");
    expect(config).toEqual({
      headers: { "Content-Type": "multipart/form-data", Accept: "application/json" },
    });
  });

  it("builds the FormData with the file, operator and fixed model fields", async () => {
    mockPost.mockResolvedValue({ data: analysis } as never);
    await uploadAudio(file, "agent-7");

    const fd = formDataArg();
    expect(fd).toBeInstanceOf(FormData);
    expect(fd.get("file")).toBe(file);
    expect(fd.get("operator_id")).toBe("agent-7");
    expect(fd.get("transcription_model_name")).toBe("base.en");
    expect(fd.get("llm_model")).toBe("gpt-4o");
  });

  it("stamps recorded_at as a second-precision UTC timestamp", async () => {
    mockPost.mockResolvedValue({ data: analysis } as never);
    await uploadAudio(file, "agent-7");

    expect(formDataArg().get("recorded_at")).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/);
  });

  it("returns the success envelope with the conversation id and analysis payload", async () => {
    mockPost.mockResolvedValue({ data: analysis } as never);

    expect(await uploadAudio(file, "agent-7")).toEqual({
      success: true,
      message: "Audio analyzed successfully",
      transcriptId: "conv-9",
      analysisData: analysis,
    });
  });

  it("rejects when the response is missing conversation_id", async () => {
    mockPost.mockResolvedValue({ data: { id: "analysis-1" } } as never);
    await expect(uploadAudio(file, "agent-7")).rejects.toThrow(
      "Invalid response structure from server"
    );
  });

  it("rejects when the response body is empty", async () => {
    mockPost.mockResolvedValue({ data: null } as never);
    await expect(uploadAudio(file, "agent-7")).rejects.toThrow(
      "Invalid response structure from server"
    );
  });

  it("surfaces a plain-string error body", async () => {
    mockPost.mockRejectedValue(responseError(400, "file too large"));
    await expect(uploadAudio(file, "agent-7")).rejects.toThrow("Upload failed: file too large");
  });

  it.each([
    ["error", { error: "bad codec" }, "bad codec"],
    ["message", { message: "bad codec" }, "bad codec"],
    ["detail", { detail: "bad codec" }, "bad codec"],
  ])("surfaces the `%s` field of an object error body", async (_field, data, expected) => {
    mockPost.mockRejectedValue(responseError(400, data));
    await expect(uploadAudio(file, "agent-7")).rejects.toThrow(`Upload failed: ${expected}`);
  });

  it("prefers `error` over `message` and `detail`", async () => {
    mockPost.mockRejectedValue(
      responseError(400, { error: "first", message: "second", detail: "third" })
    );
    await expect(uploadAudio(file, "agent-7")).rejects.toThrow("Upload failed: first");
  });

  it("falls back to the status code for an unrecognised error body", async () => {
    mockPost.mockRejectedValue(responseError(500, { unexpected: true }));
    await expect(uploadAudio(file, "agent-7")).rejects.toThrow("Upload failed: HTTP error 500");
  });

  it("reports a network error when the request never got a response", async () => {
    mockPost.mockRejectedValue(Object.assign(new Error("timeout"), { request: {} }));
    await expect(uploadAudio(file, "agent-7")).rejects.toThrow(
      "Network error: Unable to reach the server"
    );
  });

  it("passes through the message of a setup-time error", async () => {
    mockPost.mockRejectedValue(new Error("boom"));
    await expect(uploadAudio(file, "agent-7")).rejects.toThrow("boom");
  });

  it("falls back to a generic message when the error carries none", async () => {
    mockPost.mockRejectedValue({});
    await expect(uploadAudio(file, "agent-7")).rejects.toThrow("Unknown error occurred");
  });
});
