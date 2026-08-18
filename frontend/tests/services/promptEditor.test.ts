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
  listPromptVersions,
  createPromptVersion,
  restorePromptVersion,
  deletePromptVersion,
  getPromptConfig,
  linkGoldSuite,
  evaluatePrompt,
  optimizePrompt,
} from "@/services/promptEditor";

const mockApiRequest = vi.mocked(apiRequest);
beforeEach(() => vi.clearAllMocks());

// nodeId and promptField are URL-encoded by contextPath; workflowId is not.
const WF = "wf1";
const NODE = "node 1"; // encodes to node%201
const FIELD = "system/prompt"; // encodes to system%2Fprompt
const CTX = "wf1/node%201/system%2Fprompt";
const BASE = "genagent/prompt-editor";

describe("listPromptVersions", () => {
  it("GETs the versions for the encoded context", async () => {
    const versions = [{ id: "v1" }];
    mockApiRequest.mockResolvedValue(versions as never);

    const result = await listPromptVersions(WF, NODE, FIELD);

    expect(mockApiRequest).toHaveBeenCalledWith("GET", `${BASE}/versions/${CTX}`);
    expect(result).toEqual(versions);
  });
});

describe("createPromptVersion", () => {
  it("POSTs the payload to the versions endpoint", async () => {
    const payload = { label: "L", content: "C" };
    const created = { id: "v9" };
    mockApiRequest.mockResolvedValue(created as never);

    const result = await createPromptVersion(WF, NODE, FIELD, payload as never);

    expect(mockApiRequest).toHaveBeenCalledWith("POST", `${BASE}/versions/${CTX}`, payload);
    expect(result).toEqual(created);
  });
});

describe("restorePromptVersion", () => {
  it("POSTs to the restore endpoint for the version id", async () => {
    const restored = { id: "v9" };
    mockApiRequest.mockResolvedValue(restored as never);

    const result = await restorePromptVersion("v9");

    expect(mockApiRequest).toHaveBeenCalledWith("POST", `${BASE}/versions/v9/restore`);
    expect(result).toEqual(restored);
  });
});

describe("deletePromptVersion", () => {
  it("DELETEs the version by id", async () => {
    mockApiRequest.mockResolvedValue(undefined as never);

    await deletePromptVersion("v9");

    expect(mockApiRequest).toHaveBeenCalledWith("DELETE", `${BASE}/versions/v9`);
  });
});

describe("getPromptConfig", () => {
  it("GETs the config for the encoded context", async () => {
    const config = { gold_suite_id: "gs1" };
    mockApiRequest.mockResolvedValue(config as never);

    const result = await getPromptConfig(WF, NODE, FIELD);

    expect(mockApiRequest).toHaveBeenCalledWith("GET", `${BASE}/config/${CTX}`);
    expect(result).toEqual(config);
  });
});

describe("linkGoldSuite", () => {
  it("PUTs the payload to the gold-suite endpoint", async () => {
    const payload = { gold_suite_id: "gs1" };
    const config = { gold_suite_id: "gs1" };
    mockApiRequest.mockResolvedValue(config as never);

    const result = await linkGoldSuite(WF, NODE, FIELD, payload as never);

    expect(mockApiRequest).toHaveBeenCalledWith(
      "PUT",
      `${BASE}/config/${CTX}/gold-suite`,
      payload,
    );
    expect(result).toEqual(config);
  });
});

describe("evaluatePrompt", () => {
  it("POSTs the payload to the evaluate endpoint", async () => {
    const payload = { prompt: "hi" };
    const response = { score: 1 };
    mockApiRequest.mockResolvedValue(response as never);

    const result = await evaluatePrompt(WF, NODE, FIELD, payload as never);

    expect(mockApiRequest).toHaveBeenCalledWith("POST", `${BASE}/evaluate/${CTX}`, payload);
    expect(result).toEqual(response);
  });
});

describe("optimizePrompt", () => {
  it("POSTs the payload to the optimize endpoint", async () => {
    const payload = { prompt: "hi" };
    const response = { optimized_prompt: "hello" };
    mockApiRequest.mockResolvedValue(response as never);

    const result = await optimizePrompt(WF, NODE, FIELD, payload as never);

    expect(mockApiRequest).toHaveBeenCalledWith("POST", `${BASE}/optimize/${CTX}`, payload);
    expect(result).toEqual(response);
  });
});
