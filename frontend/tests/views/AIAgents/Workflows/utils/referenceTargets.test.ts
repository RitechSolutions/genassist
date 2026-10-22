import { describe, it, expect, vi, beforeEach } from "vitest";
import { Node } from "reactflow";

vi.mock("@/config/api", () => ({
  apiRequest: vi.fn(),
  getApiUrl: vi.fn(async () => "http://localhost/api/"),
  getApiUrlString: "http://localhost/api/",
  formatUploadOrNetworkError: (e: unknown) => (e instanceof Error ? e.message : String(e)),
  API_DEFAULT_TIMEOUT_MS: 1000,
  API_UPLOAD_TIMEOUT_MS: 1000,
  API_PREPROCESSING_TIMEOUT_MS: 1000,
  API_WORKFLOW_TEST_TIMEOUT_MS: 1000,
  api: { get: vi.fn(), post: vi.fn(), put: vi.fn(), patch: vi.fn(), delete: vi.fn(), request: vi.fn() },
}));

vi.mock("@/services/auth", () => ({
  hasPermission: vi.fn(() => true),
}));

import { apiRequest } from "@/config/api";
import { hasPermission } from "@/services/auth";
import { checkReferences } from "@/views/AIAgents/Workflows/utils/referenceTargets";

const mockApiRequest = vi.mocked(apiRequest);
const mockHasPermission = vi.mocked(hasPermission);

const node = (id: string, type: string, data: Record<string, unknown>): Node => ({
  id,
  type,
  position: { x: 0, y: 0 },
  data,
});

// Answers by endpoint; anything else fails the request.
const serve = (responses: Record<string, unknown>) =>
  mockApiRequest.mockImplementation(async (_method, endpoint) => {
    const path = String(endpoint).split("?")[0];
    if (!(path in responses)) throw new Error(`unexpected ${path}`);
    const response = responses[path];
    return (typeof response === "function" ? response(endpoint) : response) as never;
  });

beforeEach(() => {
  vi.clearAllMocks();
  mockHasPermission.mockReturnValue(true);
});

describe("checkReferences", () => {
  it("finds the ids that aren't listed and returns what is", async () => {
    serve({
      "llm-providers/minimal": [
        { id: "p1", name: "GPT", llm_model_provider: "openai", llm_model: "gpt-4o", is_active: 1 },
      ],
      "genagent/knowledge/items": [{ id: "kb1", name: "Docs" }],
    });
    const result = await checkReferences([
      node("a", "agentNode", { providerId: "old" }),
      node("k", "knowledgeBaseNode", { selectedBases: ["kb1"] }),
    ]);
    expect(result.missing.map((m) => `${m.kind}:${m.ids}`)).toEqual(["llmProvider:old"]);
    expect(result.targets.llmProvider?.[0]).toMatchObject({
      id: "p1",
      label: "GPT (openai - gpt-4o)",
      isActive: true,
    });
  });

  it("doesn't flag ids whose list is forbidden or fails to load", async () => {
    const quiet = vi.spyOn(console, "error").mockImplementation(() => {});
    serve({ "llm-providers/minimal": null });
    const result = await checkReferences([
      node("a", "agentNode", { providerId: "old" }),
      node("d", "sqlNode", { dataSourceId: "ds-old" }),
    ]);
    expect(result.missing).toEqual([]);
    expect(result.targets).toEqual({});
    quiet.mockRestore();
  });

  it("skips configuration vars without permission to read them", async () => {
    mockHasPermission.mockReturnValue(false);
    serve({});
    const result = await checkReferences([node("s", "slackMessageNode", { app_settings_id: "old" })]);
    expect(result.missing).toEqual([]);
    expect(mockApiRequest).not.toHaveBeenCalled();
  });

  it("leaves out the kinds it's told to skip", async () => {
    serve({});
    const result = await checkReferences(
      [node("t", "ttsNode", { audioProviderId: "old" })],
      ["audioProvider"]
    );
    expect(result.missing).toEqual([]);
    expect(mockApiRequest).not.toHaveBeenCalled();
  });

  it("checks workflows against the executor's list and names them after their agent", async () => {
    const input = node("in", "chatInputNode", { inputSchema: { topic: { type: "string" } } });
    serve({
      "genagent/workflow/": [
        { id: "w1", name: "Friendly", version: "1.1", nodes: [] },
        { id: "w2", name: "No agent", version: "2.0", nodes: [input] },
      ],
      // Agent Studio's list leaves out workflows without a live agent.
      "genagent/workflow/minimal": [
        { id: "w1", name: "Friendly", version: "1.1", agent_name: "Order Help", is_active_version: true },
      ],
    });
    const result = await checkReferences([node("e", "workflowExecutorNode", { workflowId: "w2" })]);
    expect(result.missing).toEqual([]);
    expect(result.targets.workflow?.map((t) => [t.label, t.inputs])).toEqual([
      ["Order Help · Friendly (v1.1, active)", undefined],
      ["No agent (v2.0)", ["topic"]],
    ]);
  });

  it("gives ML models their features and baseline column as inputs", async () => {
    serve({
      "ml-models": [
        { id: "m1", name: "Churn", features: ["age", "plan"], inference_params: null },
        {
          id: "m2",
          name: "Ratio",
          features: ["spend"],
          inference_params: { ratioBaselineColumn: "baseline" },
        },
      ],
    });
    const result = await checkReferences([node("i", "mlModelInferenceNode", { modelId: "gone" })]);
    expect(result.targets.mlModel?.map((t) => t.inputs)).toEqual([
      ["age", "plan"],
      ["spend", "baseline"],
    ]);
  });

  it("reads every page of agents", async () => {
    const page = (start: number, count: number) =>
      Array.from({ length: count }, (_, i) => ({
        id: `ag${start + i}`,
        name: `Agent ${start + i}`,
        is_active: true,
      }));
    serve({
      "genagent/agents/configs/list": (endpoint: string) =>
        endpoint.includes("skip=0")
          ? { items: page(0, 100), total: 101, page: 1, page_size: 100 }
          : { items: page(100, 1), total: 101, page: 2, page_size: 100 },
    });
    const result = await checkReferences([
      node("w", "createWorkflowScheduleNode", { agentId: "ag100" }),
    ]);
    expect(result.missing).toEqual([]);
    expect(result.targets.agent).toHaveLength(101);
  });
});
