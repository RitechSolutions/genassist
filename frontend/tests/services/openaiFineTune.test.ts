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
  getFineTunableModels,
  listFineTuneJobs,
  syncFineTuneJobs,
  getFineTuneJob,
  createFineTuneJob,
  cancelFineTuneJob,
  listOpenAIFiles,
  generateTrainingFileFromConversations,
} from "@/services/openaiFineTune";

const mockApiRequest = vi.mocked(apiRequest);
beforeEach(() => vi.clearAllMocks());

describe("getFineTunableModels", () => {
  it("returns a plain array unchanged", async () => {
    const models = ["a", "b"];
    mockApiRequest.mockResolvedValue(models as never);
    expect(await getFineTunableModels()).toBe(models);
    expect(mockApiRequest).toHaveBeenCalledWith("GET", "openai/models/fine-tunable");
  });

  it("unwraps a paginated response via .data", async () => {
    const data = ["a"];
    mockApiRequest.mockResolvedValue({ data } as never);
    expect(await getFineTunableModels()).toBe(data);
  });

  it("returns [] when the response is null", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    expect(await getFineTunableModels()).toEqual([]);
  });

  it("returns [] for an object without a data field", async () => {
    mockApiRequest.mockResolvedValue({ foo: 1 } as never);
    expect(await getFineTunableModels()).toEqual([]);
  });
});

describe("listFineTuneJobs", () => {
  it("returns the array of jobs", async () => {
    const jobs = [{ id: "j1" }];
    mockApiRequest.mockResolvedValue(jobs as never);
    expect(await listFineTuneJobs()).toBe(jobs);
    expect(mockApiRequest).toHaveBeenCalledWith("GET", "openai/fine-tuning/jobs");
  });

  it("unwraps a paginated response", async () => {
    const data = [{ id: "j1" }];
    mockApiRequest.mockResolvedValue({ data } as never);
    expect(await listFineTuneJobs()).toBe(data);
  });
});

describe("syncFineTuneJobs", () => {
  it("posts to the sync endpoint and normalizes the list", async () => {
    const jobs = [{ id: "j1" }];
    mockApiRequest.mockResolvedValue(jobs as never);
    expect(await syncFineTuneJobs()).toBe(jobs);
    expect(mockApiRequest).toHaveBeenCalledWith("POST", "openai/fine-tuning/jobs/sync");
  });

  it("returns [] when the response is null", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    expect(await syncFineTuneJobs()).toEqual([]);
  });
});

describe("getFineTuneJob", () => {
  it("appends ?sync=True by default", async () => {
    const job = { id: "j1" };
    mockApiRequest.mockResolvedValue(job as never);
    expect(await getFineTuneJob("j1")).toBe(job);
    expect(mockApiRequest).toHaveBeenCalledWith("GET", "openai/fine-tuning/jobs/j1?sync=True");
  });

  it("omits the sync query when sync is false", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    expect(await getFineTuneJob("j1", false)).toBeNull();
    expect(mockApiRequest).toHaveBeenCalledWith("GET", "openai/fine-tuning/jobs/j1");
  });
});

describe("createFineTuneJob", () => {
  it("posts a JSON-cloned payload", async () => {
    const payload = { base_model: "x", nested: { a: 1 } } as never;
    const job = { id: "j1" };
    mockApiRequest.mockResolvedValue(job as never);
    expect(await createFineTuneJob(payload)).toBe(job);
    expect(mockApiRequest).toHaveBeenCalledWith("POST", "openai/fine-tuning/jobs", {
      base_model: "x",
      nested: { a: 1 },
    });
  });
});

describe("cancelFineTuneJob", () => {
  it("posts to the cancel endpoint", async () => {
    const resp = { status: "cancelled" };
    mockApiRequest.mockResolvedValue(resp as never);
    expect(await cancelFineTuneJob("j1")).toBe(resp);
    expect(mockApiRequest).toHaveBeenCalledWith("POST", "openai/fine-tuning/jobs/j1/cancel");
  });
});

describe("listOpenAIFiles", () => {
  it("returns the array of files", async () => {
    const files = [{ id: "f1" }];
    mockApiRequest.mockResolvedValue(files as never);
    expect(await listOpenAIFiles()).toBe(files);
    expect(mockApiRequest).toHaveBeenCalledWith("GET", "openai/files");
  });

  it("returns [] when the response is null", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    expect(await listOpenAIFiles()).toEqual([]);
  });
});

describe("generateTrainingFileFromConversations", () => {
  it("posts the payload verbatim and returns the result", async () => {
    const payload = {
      conversation_ids: ["c1"],
      memory_conversation_ids: ["m1"],
      include_tools: true,
      upload_to_openai: true,
    };
    const result = { id: "f1" };
    mockApiRequest.mockResolvedValue(result as never);
    expect(await generateTrainingFileFromConversations(payload)).toBe(result);
    expect(mockApiRequest).toHaveBeenCalledWith(
      "POST",
      "openai/fine-tuning/generate-from-conversations",
      payload
    );
  });
});
