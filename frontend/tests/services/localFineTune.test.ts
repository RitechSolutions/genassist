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

import { AxiosError } from "axios";
import { apiRequest } from "@/config/api";
import {
  getLocalFineTuneErrorMessage,
  listLocalFineTuneSupportedModels,
  listLocalFineTuneJobs,
  getLocalFineTuneJob,
  listLocalFineTuneJobEvents,
  createLocalFineTuneJob,
  cancelLocalFineTuneJob,
  deleteLocalFineTuneJobFiles,
  createDeployment,
  listDeployments,
  getDeployment,
  stopDeployment,
  checkDeploymentHealth,
  listSystemGpus,
  testDeploymentInference,
} from "@/services/localFineTune";

const mockApiRequest = vi.mocked(apiRequest);
beforeEach(() => vi.clearAllMocks());

describe("getLocalFineTuneErrorMessage", () => {
  it("prefers error_detail from an AxiosError response", () => {
    const err = new AxiosError("axios message");
    err.response = {
      data: { error_detail: "detail-a", error: "err-b", detail: "det-c", message: "msg-d" },
    } as never;
    expect(getLocalFineTuneErrorMessage(err, "fb")).toBe("detail-a");
  });

  it("falls back through error, detail, then message in order", () => {
    const e1 = new AxiosError("m");
    e1.response = { data: { error: "err-b", detail: "det-c" } } as never;
    expect(getLocalFineTuneErrorMessage(e1, "fb")).toBe("err-b");

    const e2 = new AxiosError("m");
    e2.response = { data: { detail: "det-c", message: "msg-d" } } as never;
    expect(getLocalFineTuneErrorMessage(e2, "fb")).toBe("det-c");

    const e3 = new AxiosError("m");
    e3.response = { data: { message: "msg-d" } } as never;
    expect(getLocalFineTuneErrorMessage(e3, "fb")).toBe("msg-d");
  });

  it("uses the axios error message when the response carries no detail fields", () => {
    const err = new AxiosError("network boom");
    expect(getLocalFineTuneErrorMessage(err, "fb")).toBe("network boom");
  });

  it("returns the fallback for an AxiosError with no message and no detail", () => {
    const err = new AxiosError("");
    expect(getLocalFineTuneErrorMessage(err, "fallback-x")).toBe("fallback-x");
  });

  it("uses a plain Error message", () => {
    expect(getLocalFineTuneErrorMessage(new Error("plain"), "fb")).toBe("plain");
  });

  it("returns the fallback for non-error values", () => {
    expect(getLocalFineTuneErrorMessage("nope", "fallback-y")).toBe("fallback-y");
    expect(getLocalFineTuneErrorMessage(null, "fallback-z")).toBe("fallback-z");
  });
});

describe("listLocalFineTuneSupportedModels", () => {
  it("requests supported models with default pagination and returns the array", async () => {
    const models = [{ id: "m1" }];
    mockApiRequest.mockResolvedValue(models as never);
    const res = await listLocalFineTuneSupportedModels();
    expect(mockApiRequest).toHaveBeenCalledWith(
      "GET",
      "local-fine-tuning/supported-models",
      undefined,
      { params: { skip: 0, limit: 10 } }
    );
    expect(res).toBe(models);
  });

  it("passes custom skip and limit", async () => {
    mockApiRequest.mockResolvedValue([] as never);
    await listLocalFineTuneSupportedModels(5, 25);
    expect(mockApiRequest).toHaveBeenCalledWith(
      "GET",
      "local-fine-tuning/supported-models",
      undefined,
      { params: { skip: 5, limit: 25 } }
    );
  });

  it("falls back to [] when the response is not an array", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    expect(await listLocalFineTuneSupportedModels()).toEqual([]);
  });
});

describe("listLocalFineTuneJobs", () => {
  it("returns the jobs array", async () => {
    const jobs = [{ id: "j1" }];
    mockApiRequest.mockResolvedValue(jobs as never);
    expect(await listLocalFineTuneJobs()).toBe(jobs);
    expect(mockApiRequest).toHaveBeenCalledWith("GET", "local-fine-tuning/jobs");
  });

  it("falls back to [] when not an array", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    expect(await listLocalFineTuneJobs()).toEqual([]);
  });
});

describe("getLocalFineTuneJob", () => {
  it("returns the job", async () => {
    const job = { id: "j1" };
    mockApiRequest.mockResolvedValue(job as never);
    expect(await getLocalFineTuneJob("j1")).toBe(job);
    expect(mockApiRequest).toHaveBeenCalledWith("GET", "local-fine-tuning/jobs/j1");
  });

  it("returns null on error", async () => {
    mockApiRequest.mockRejectedValue(new Error("boom"));
    expect(await getLocalFineTuneJob("j1")).toBeNull();
  });
});

describe("listLocalFineTuneJobEvents", () => {
  it("returns the events array", async () => {
    const events = [{ id: "e1" }];
    mockApiRequest.mockResolvedValue(events as never);
    expect(await listLocalFineTuneJobEvents("j1")).toBe(events);
    expect(mockApiRequest).toHaveBeenCalledWith("GET", "local-fine-tuning/jobs/j1/events");
  });

  it("falls back to [] when not an array", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    expect(await listLocalFineTuneJobEvents("j1")).toEqual([]);
  });

  it("returns [] on error", async () => {
    mockApiRequest.mockRejectedValue(new Error("boom"));
    expect(await listLocalFineTuneJobEvents("j1")).toEqual([]);
  });
});

describe("createLocalFineTuneJob", () => {
  it("posts the payload and returns the created job", async () => {
    const payload = { base_model: "x" } as never;
    const job = { id: "j1" };
    mockApiRequest.mockResolvedValue(job as never);
    expect(await createLocalFineTuneJob(payload)).toBe(job);
    expect(mockApiRequest).toHaveBeenCalledWith("POST", "local-fine-tuning/jobs", payload);
  });

  it("throws when apiRequest resolves falsy", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    await expect(createLocalFineTuneJob({} as never)).rejects.toThrow(
      "Failed to create local fine-tune job"
    );
  });
});

describe("cancelLocalFineTuneJob", () => {
  it("posts to the cancel endpoint and returns the job", async () => {
    const job = { id: "j1" };
    mockApiRequest.mockResolvedValue(job as never);
    expect(await cancelLocalFineTuneJob("j1")).toBe(job);
    expect(mockApiRequest).toHaveBeenCalledWith("POST", "local-fine-tuning/jobs/j1/cancel");
  });

  it("throws when apiRequest resolves falsy", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    await expect(cancelLocalFineTuneJob("j1")).rejects.toThrow(
      "Failed to cancel local fine-tune job"
    );
  });
});

describe("deleteLocalFineTuneJobFiles", () => {
  it("uses default deletion flags", async () => {
    const resp = { deleted: true };
    mockApiRequest.mockResolvedValue(resp as never);
    expect(await deleteLocalFineTuneJobFiles("j1")).toBe(resp);
    expect(mockApiRequest).toHaveBeenCalledWith(
      "DELETE",
      "local-fine-tuning/jobs/j1/files",
      undefined,
      { params: { delete_data_files: true, delete_checkpoints: true, delete_model: false } }
    );
  });

  it("respects provided options", async () => {
    mockApiRequest.mockResolvedValue({ deleted: true } as never);
    await deleteLocalFineTuneJobFiles("j2", {
      delete_data_files: false,
      delete_checkpoints: false,
      delete_model: true,
    });
    expect(mockApiRequest).toHaveBeenCalledWith(
      "DELETE",
      "local-fine-tuning/jobs/j2/files",
      undefined,
      { params: { delete_data_files: false, delete_checkpoints: false, delete_model: true } }
    );
  });

  it("throws when apiRequest resolves falsy", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    await expect(deleteLocalFineTuneJobFiles("j3")).rejects.toThrow(
      "Failed to delete local fine-tune job files"
    );
  });
});

describe("createDeployment", () => {
  it("posts the payload and returns the deployment", async () => {
    const payload = { job_id: "j1" } as never;
    const dep = { id: "d1" };
    mockApiRequest.mockResolvedValue(dep as never);
    expect(await createDeployment(payload)).toBe(dep);
    expect(mockApiRequest).toHaveBeenCalledWith("POST", "local-fine-tuning/deployments", payload);
  });

  it("throws when apiRequest resolves falsy", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    await expect(createDeployment({} as never)).rejects.toThrow("Failed to create deployment");
  });
});

describe("listDeployments", () => {
  it("returns the deployments array", async () => {
    const deps = [{ id: "d1" }];
    mockApiRequest.mockResolvedValue(deps as never);
    expect(await listDeployments()).toBe(deps);
    expect(mockApiRequest).toHaveBeenCalledWith("GET", "local-fine-tuning/deployments");
  });

  it("falls back to [] when not an array", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    expect(await listDeployments()).toEqual([]);
  });
});

describe("getDeployment", () => {
  it("returns the deployment", async () => {
    const dep = { id: "d1" };
    mockApiRequest.mockResolvedValue(dep as never);
    expect(await getDeployment("d1")).toBe(dep);
    expect(mockApiRequest).toHaveBeenCalledWith("GET", "local-fine-tuning/deployments/d1");
  });

  it("returns null on error", async () => {
    mockApiRequest.mockRejectedValue(new Error("boom"));
    expect(await getDeployment("d1")).toBeNull();
  });
});

describe("stopDeployment", () => {
  it("deletes the deployment and returns the response", async () => {
    const resp = { status: "stopped" };
    mockApiRequest.mockResolvedValue(resp as never);
    expect(await stopDeployment("d1")).toBe(resp);
    expect(mockApiRequest).toHaveBeenCalledWith("DELETE", "local-fine-tuning/deployments/d1");
  });

  it("throws when apiRequest resolves falsy", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    await expect(stopDeployment("d1")).rejects.toThrow("Failed to stop deployment");
  });
});

describe("checkDeploymentHealth", () => {
  it("fetches deployment health", async () => {
    const health = { status: "healthy" };
    mockApiRequest.mockResolvedValue(health as never);
    expect(await checkDeploymentHealth("d1")).toBe(health);
    expect(mockApiRequest).toHaveBeenCalledWith("GET", "local-fine-tuning/deployments/d1/health");
  });

  it("throws when apiRequest resolves falsy", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    await expect(checkDeploymentHealth("d1")).rejects.toThrow("Failed to fetch deployment health");
  });
});

describe("listSystemGpus", () => {
  it("returns gpus when cuda is available", async () => {
    const gpus = [{ name: "A100" }];
    mockApiRequest.mockResolvedValue({ cuda_available: true, gpus } as never);
    expect(await listSystemGpus()).toBe(gpus);
    expect(mockApiRequest).toHaveBeenCalledWith("GET", "local-fine-tuning/system/gpus");
  });

  it("returns [] when cuda is unavailable", async () => {
    mockApiRequest.mockResolvedValue({ cuda_available: false, gpus: [{ name: "A100" }] } as never);
    expect(await listSystemGpus()).toEqual([]);
  });

  it("returns [] when the response is falsy", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    expect(await listSystemGpus()).toEqual([]);
  });
});

describe("testDeploymentInference", () => {
  it("posts the message and returns the content", async () => {
    mockApiRequest.mockResolvedValue({ content: "hello" } as never);
    expect(await testDeploymentInference("d1", "hi")).toBe("hello");
    expect(mockApiRequest).toHaveBeenCalledWith(
      "POST",
      "local-fine-tuning/deployments/d1/test-inference",
      { message: "hi" }
    );
  });

  it("throws when apiRequest resolves falsy", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    await expect(testDeploymentInference("d1", "hi")).rejects.toThrow("Inference call failed");
  });
});
