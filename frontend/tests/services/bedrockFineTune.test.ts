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
  getBedrockFineTunableModels,
  listBedrockFineTuneJobs,
  syncBedrockFineTuneJobs,
  getBedrockFineTuneJob,
  createBedrockFineTuneJob,
  cancelBedrockFineTuneJob,
  deleteBedrockFineTuneJob,
  deployBedrockCustomModel,
  undeployBedrockCustomModel,
  listBedrockTrainingFiles,
  generateBedrockTrainingFileFromConversations,
} from "@/services/bedrockFineTune";

const mockApiRequest = vi.mocked(apiRequest);
beforeEach(() => vi.clearAllMocks());

describe("getBedrockFineTunableModels", () => {
  it("returns a plain array unchanged", async () => {
    const models = ["a", "b"];
    mockApiRequest.mockResolvedValue(models as never);
    expect(await getBedrockFineTunableModels()).toBe(models);
    expect(mockApiRequest).toHaveBeenCalledWith("GET", "bedrock/models/fine-tunable");
  });

  it("unwraps a paginated response via .data", async () => {
    const data = ["a"];
    mockApiRequest.mockResolvedValue({ data } as never);
    expect(await getBedrockFineTunableModels()).toBe(data);
  });

  it("returns [] when the response is null", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    expect(await getBedrockFineTunableModels()).toEqual([]);
  });

  it("returns [] for an object without a data field", async () => {
    mockApiRequest.mockResolvedValue({ foo: 1 } as never);
    expect(await getBedrockFineTunableModels()).toEqual([]);
  });
});

describe("listBedrockFineTuneJobs", () => {
  it("returns the array of jobs", async () => {
    const jobs = [{ id: "j1" }];
    mockApiRequest.mockResolvedValue(jobs as never);
    expect(await listBedrockFineTuneJobs()).toBe(jobs);
    expect(mockApiRequest).toHaveBeenCalledWith("GET", "bedrock/fine-tuning/jobs");
  });

  it("unwraps a paginated response", async () => {
    const data = [{ id: "j1" }];
    mockApiRequest.mockResolvedValue({ data } as never);
    expect(await listBedrockFineTuneJobs()).toBe(data);
  });
});

describe("syncBedrockFineTuneJobs", () => {
  it("posts to the sync endpoint and normalizes the list", async () => {
    const jobs = [{ id: "j1" }];
    mockApiRequest.mockResolvedValue(jobs as never);
    expect(await syncBedrockFineTuneJobs()).toBe(jobs);
    expect(mockApiRequest).toHaveBeenCalledWith("POST", "bedrock/fine-tuning/jobs/sync");
  });

  it("returns [] when the response is null", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    expect(await syncBedrockFineTuneJobs()).toEqual([]);
  });
});

describe("getBedrockFineTuneJob", () => {
  it("appends ?sync=True by default", async () => {
    const job = { id: "j1" };
    mockApiRequest.mockResolvedValue(job as never);
    expect(await getBedrockFineTuneJob("j1")).toBe(job);
    expect(mockApiRequest).toHaveBeenCalledWith("GET", "bedrock/fine-tuning/jobs/j1?sync=True");
  });

  it("omits the sync query when sync is false", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    expect(await getBedrockFineTuneJob("j1", false)).toBeNull();
    expect(mockApiRequest).toHaveBeenCalledWith("GET", "bedrock/fine-tuning/jobs/j1");
  });
});

describe("createBedrockFineTuneJob", () => {
  it("posts a JSON-cloned payload", async () => {
    const payload = { base_model: "x", nested: { a: 1 } } as never;
    const job = { id: "j1" };
    mockApiRequest.mockResolvedValue(job as never);
    expect(await createBedrockFineTuneJob(payload)).toBe(job);
    expect(mockApiRequest).toHaveBeenCalledWith("POST", "bedrock/fine-tuning/jobs", {
      base_model: "x",
      nested: { a: 1 },
    });
  });
});

describe("cancelBedrockFineTuneJob", () => {
  it("posts to the cancel endpoint", async () => {
    const job = { id: "j1" };
    mockApiRequest.mockResolvedValue(job as never);
    expect(await cancelBedrockFineTuneJob("j1")).toBe(job);
    expect(mockApiRequest).toHaveBeenCalledWith("POST", "bedrock/fine-tuning/jobs/j1/cancel");
  });
});

describe("deleteBedrockFineTuneJob", () => {
  it("deletes the job", async () => {
    mockApiRequest.mockResolvedValue(undefined as never);
    await deleteBedrockFineTuneJob("j1");
    expect(mockApiRequest).toHaveBeenCalledWith("DELETE", "bedrock/fine-tuning/jobs/j1");
  });
});

describe("deployBedrockCustomModel", () => {
  it("posts to the deploy endpoint", async () => {
    const job = { id: "j1" };
    mockApiRequest.mockResolvedValue(job as never);
    expect(await deployBedrockCustomModel("j1")).toBe(job);
    expect(mockApiRequest).toHaveBeenCalledWith("POST", "bedrock/fine-tuning/jobs/j1/deploy");
  });
});

describe("undeployBedrockCustomModel", () => {
  it("posts to the undeploy endpoint", async () => {
    const job = { id: "j1" };
    mockApiRequest.mockResolvedValue(job as never);
    expect(await undeployBedrockCustomModel("j1")).toBe(job);
    expect(mockApiRequest).toHaveBeenCalledWith("POST", "bedrock/fine-tuning/jobs/j1/undeploy");
  });
});

describe("listBedrockTrainingFiles", () => {
  it("returns the array of training files", async () => {
    const files = [{ id: "f1" }];
    mockApiRequest.mockResolvedValue(files as never);
    expect(await listBedrockTrainingFiles()).toBe(files);
    expect(mockApiRequest).toHaveBeenCalledWith("GET", "bedrock/training-files");
  });

  it("returns [] when the response is null", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    expect(await listBedrockTrainingFiles()).toEqual([]);
  });
});

describe("generateBedrockTrainingFileFromConversations", () => {
  it("posts the payload with upload_to_s3 true and returns the result", async () => {
    const result = { file_id: "f1" };
    mockApiRequest.mockResolvedValue(result as never);
    const res = await generateBedrockTrainingFileFromConversations({
      conversation_ids: ["c1"],
      memory_conversation_ids: ["m1"],
    });
    expect(res).toBe(result);
    expect(mockApiRequest).toHaveBeenCalledWith(
      "POST",
      "bedrock/fine-tuning/generate-from-conversations",
      { conversation_ids: ["c1"], memory_conversation_ids: ["m1"], upload_to_s3: true }
    );
  });
});
