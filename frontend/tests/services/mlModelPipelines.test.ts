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
  getModelPipelineConfigs,
  getPipelineConfig,
  createPipelineConfig,
  updatePipelineConfig,
  deletePipelineConfig,
  getModelPipelineRuns,
  getPipelineRun,
  createPipelineRun,
  promotePipelineRun,
  getPipelineRunArtifacts,
} from "@/services/mlModelPipelines";

const mockApiRequest = vi.mocked(apiRequest);

beforeEach(() => {
  vi.clearAllMocks();
  vi.spyOn(console, "error").mockImplementation(() => {});
});

describe("getModelPipelineConfigs", () => {
  it("returns the configs array", async () => {
    const configs = [{ id: "c1" }];
    mockApiRequest.mockResolvedValue(configs as never);
    expect(await getModelPipelineConfigs("m1")).toBe(configs);
    expect(mockApiRequest).toHaveBeenCalledWith("GET", "ml-models/m1/pipeline-configs");
  });

  it("falls back to [] when the response is falsy", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    expect(await getModelPipelineConfigs("m1")).toEqual([]);
  });

  it("rethrows on error", async () => {
    mockApiRequest.mockRejectedValue(new Error("boom"));
    await expect(getModelPipelineConfigs("m1")).rejects.toThrow("boom");
  });
});

describe("getPipelineConfig", () => {
  it("returns the config", async () => {
    const config = { id: "c1" };
    mockApiRequest.mockResolvedValue(config as never);
    expect(await getPipelineConfig("m1", "c1")).toBe(config);
    expect(mockApiRequest).toHaveBeenCalledWith("GET", "ml-models/m1/pipeline-configs/c1");
  });

  it("falls back to null when the response is nullish", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    expect(await getPipelineConfig("m1", "c1")).toBeNull();
  });

  it("rethrows on error", async () => {
    mockApiRequest.mockRejectedValue(new Error("boom"));
    await expect(getPipelineConfig("m1", "c1")).rejects.toThrow("boom");
  });
});

describe("createPipelineConfig", () => {
  it("posts the config and returns the created config", async () => {
    const config = { name: "x" } as never;
    const created = { id: "c1" };
    mockApiRequest.mockResolvedValue(created as never);
    expect(await createPipelineConfig("m1", config)).toBe(created);
    expect(mockApiRequest).toHaveBeenCalledWith("POST", "ml-models/m1/pipeline-configs", config);
  });

  it("throws when the response is falsy", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    await expect(createPipelineConfig("m1", {} as never)).rejects.toThrow(
      "Failed to create pipeline config"
    );
  });
});

describe("updatePipelineConfig", () => {
  it("puts the config and returns the updated config", async () => {
    const config = { name: "x" } as never;
    const updated = { id: "c1" };
    mockApiRequest.mockResolvedValue(updated as never);
    expect(await updatePipelineConfig("m1", "c1", config)).toBe(updated);
    expect(mockApiRequest).toHaveBeenCalledWith(
      "PUT",
      "ml-models/m1/pipeline-configs/c1",
      config
    );
  });

  it("throws when the response is falsy", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    await expect(updatePipelineConfig("m1", "c1", {} as never)).rejects.toThrow(
      "Failed to update pipeline config"
    );
  });
});

describe("deletePipelineConfig", () => {
  it("deletes the config", async () => {
    mockApiRequest.mockResolvedValue(undefined as never);
    await deletePipelineConfig("m1", "c1");
    expect(mockApiRequest).toHaveBeenCalledWith("DELETE", "ml-models/m1/pipeline-configs/c1");
  });

  it("rethrows on error", async () => {
    mockApiRequest.mockRejectedValue(new Error("boom"));
    await expect(deletePipelineConfig("m1", "c1")).rejects.toThrow("boom");
  });
});

describe("getModelPipelineRuns", () => {
  it("returns the runs array", async () => {
    const runs = [{ id: "r1" }];
    mockApiRequest.mockResolvedValue(runs as never);
    expect(await getModelPipelineRuns("m1")).toBe(runs);
    expect(mockApiRequest).toHaveBeenCalledWith("GET", "ml-models/m1/pipeline-runs");
  });

  it("falls back to [] when the response is falsy", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    expect(await getModelPipelineRuns("m1")).toEqual([]);
  });
});

describe("getPipelineRun", () => {
  it("returns the run", async () => {
    const run = { id: "r1" };
    mockApiRequest.mockResolvedValue(run as never);
    expect(await getPipelineRun("m1", "r1")).toBe(run);
    expect(mockApiRequest).toHaveBeenCalledWith("GET", "ml-models/m1/pipeline-runs/r1");
  });

  it("falls back to null when the response is nullish", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    expect(await getPipelineRun("m1", "r1")).toBeNull();
  });
});

describe("createPipelineRun", () => {
  it("posts the run and returns the created run", async () => {
    const run = { trigger: "manual" } as never;
    const created = { id: "r1" };
    mockApiRequest.mockResolvedValue(created as never);
    expect(await createPipelineRun("m1", run)).toBe(created);
    expect(mockApiRequest).toHaveBeenCalledWith("POST", "ml-models/m1/pipeline-runs", run);
  });

  it("throws when the response is falsy", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    await expect(createPipelineRun("m1", {} as never)).rejects.toThrow(
      "Failed to create pipeline run"
    );
  });
});

describe("promotePipelineRun", () => {
  it("posts to the promote endpoint", async () => {
    mockApiRequest.mockResolvedValue(undefined as never);
    await promotePipelineRun("m1", "r1");
    expect(mockApiRequest).toHaveBeenCalledWith("POST", "ml-models/m1/pipeline-runs/r1/promote");
  });

  it("rethrows on error", async () => {
    mockApiRequest.mockRejectedValue(new Error("boom"));
    await expect(promotePipelineRun("m1", "r1")).rejects.toThrow("boom");
  });
});

describe("getPipelineRunArtifacts", () => {
  it("returns the artifacts array", async () => {
    const artifacts = [{ id: "a1" }];
    mockApiRequest.mockResolvedValue(artifacts as never);
    expect(await getPipelineRunArtifacts("m1", "r1")).toBe(artifacts);
    expect(mockApiRequest).toHaveBeenCalledWith(
      "GET",
      "ml-models/m1/pipeline-runs/r1/artifacts"
    );
  });

  it("falls back to [] when the response is falsy", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    expect(await getPipelineRunArtifacts("m1", "r1")).toEqual([]);
  });
});
