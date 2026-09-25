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
  getPromptHistory,
  createPromptVersion,
  deletePromptVersion,
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

describe("getPromptHistory", () => {
  it("GETs the history for the encoded context", async () => {
    const history = { versions: [{ id: "v1" }], node_missing: false };
    mockApiRequest.mockResolvedValue(history as never);

    const result = await getPromptHistory(WF, NODE, FIELD);

    expect(mockApiRequest).toHaveBeenCalledWith("GET", `${BASE}/history/${CTX}`);
    expect(result).toEqual(history);
  });

  it("appends the node type hint, encoded, only when one is given", async () => {
    mockApiRequest.mockResolvedValue({} as never);

    await getPromptHistory(WF, NODE, FIELD, "agent/Node");
    expect(mockApiRequest).toHaveBeenLastCalledWith(
      "GET",
      `${BASE}/history/${CTX}?node_type=agent%2FNode`,
    );

    await getPromptHistory(WF, NODE, FIELD, "");
    expect(mockApiRequest).toHaveBeenLastCalledWith(
      "GET",
      `${BASE}/history/${CTX}`,
    );
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

describe("deletePromptVersion", () => {
  it("DELETEs the version by id", async () => {
    mockApiRequest.mockResolvedValue(undefined as never);

    await deletePromptVersion("v9");

    expect(mockApiRequest).toHaveBeenCalledWith("DELETE", `${BASE}/versions/v9`);
  });

  it("resolves on the empty body a 204 produces", async () => {
    mockApiRequest.mockResolvedValue("" as never);

    await expect(deletePromptVersion("v9")).resolves.toBeUndefined();
  });

  it("rejects on null, which apiRequest returns for a 403", async () => {
    mockApiRequest.mockResolvedValue(null as never);

    await expect(deletePromptVersion("v9")).rejects.toThrow(/Not allowed/);
  });
});

describe("linkGoldSuite", () => {
  it("PUTs the payload to the gold-suite endpoint", async () => {
    const payload = { suite_id: "gs1" };
    const config = { gold_suite_id: "gs1" };
    mockApiRequest.mockResolvedValue(config as never);

    const result = await linkGoldSuite(WF, NODE, FIELD, payload);

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
