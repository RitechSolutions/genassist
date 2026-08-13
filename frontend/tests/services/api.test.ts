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

// getAgentIntegrationKey depends on the apiKeys service; mock it so the flow is hermetic.
vi.mock("@/services/apiKeys", () => ({
  getApiKeys: vi.fn(),
  revealApiKey: vi.fn(),
}));

import { apiRequest } from "@/config/api";
import { getApiKeys, revealApiKey } from "@/services/apiKeys";
import {
  getAllAgentConfigs,
  getAgentConfigsList,
  getAgentConfig,
  getIntegrationConfig,
  createAgentConfig,
  getRagFromSchema,
  updateAgentConfig,
  deleteAgentConfig,
  deleteWelcomeImage,
  initializeAgent,
  queryAgent,
  getAllKnowledgeItems,
  getKnowledgeItemsList,
  getKnowledgeItem,
  createKnowledgeItem,
  updateKnowledgeItem,
  deleteKnowledgeItem,
  finalizeKnowledgeItem,
  executeKnowledgeBaseSyncronizationManually,
  getAllTools,
  getTool,
  createTool,
  updateTool,
  deleteTool,
  testPythonCode,
  generatePythonTemplate,
  generatePythonTemplateFromTool,
  testPythonCodeWithSchema,
  getAgentIntegrationKey,
} from "@/services/api";

const mockApiRequest = vi.mocked(apiRequest);
const mockGetApiKeys = vi.mocked(getApiKeys);
const mockRevealApiKey = vi.mocked(revealApiKey);

beforeEach(() => vi.clearAllMocks());

describe("agent config endpoints", () => {
  it("getAllAgentConfigs GETs the configs collection and returns the result", async () => {
    const configs = [{ id: "a1" }];
    mockApiRequest.mockResolvedValue(configs);

    const result = await getAllAgentConfigs();

    expect(mockApiRequest).toHaveBeenCalledWith("GET", "genagent/agents/configs");
    expect(result).toBe(configs);
  });

  it("getAgentConfigsList builds a skip/limit query with defaults", async () => {
    mockApiRequest.mockResolvedValue({ items: [] });

    await getAgentConfigsList();

    expect(mockApiRequest).toHaveBeenCalledWith(
      "GET",
      "genagent/agents/configs/list?skip=0&limit=20"
    );
  });

  it("getAgentConfigsList computes skip from page and pageSize", async () => {
    mockApiRequest.mockResolvedValue({ items: [] });

    await getAgentConfigsList(3, 10);

    expect(mockApiRequest).toHaveBeenCalledWith(
      "GET",
      "genagent/agents/configs/list?skip=20&limit=10"
    );
  });

  it("getAgentConfigsList appends is_system=true when provided", async () => {
    mockApiRequest.mockResolvedValue({ items: [] });

    await getAgentConfigsList(1, 20, true);

    expect(mockApiRequest).toHaveBeenCalledWith(
      "GET",
      "genagent/agents/configs/list?skip=0&limit=20&is_system=true"
    );
  });

  it("getAgentConfigsList appends is_system=false when explicitly false", async () => {
    mockApiRequest.mockResolvedValue({ items: [] });

    await getAgentConfigsList(1, 20, false);

    expect(mockApiRequest).toHaveBeenCalledWith(
      "GET",
      "genagent/agents/configs/list?skip=0&limit=20&is_system=false"
    );
  });

  it("getAgentConfigsList omits is_system when null", async () => {
    mockApiRequest.mockResolvedValue({ items: [] });

    await getAgentConfigsList(1, 20, null);

    expect(mockApiRequest).toHaveBeenCalledWith(
      "GET",
      "genagent/agents/configs/list?skip=0&limit=20"
    );
  });

  it("getAgentConfig GETs a single config by id", async () => {
    const cfg = { id: "abc" };
    mockApiRequest.mockResolvedValue(cfg);

    const result = await getAgentConfig("abc");

    expect(mockApiRequest).toHaveBeenCalledWith("GET", "genagent/agents/configs/abc");
    expect(result).toBe(cfg);
  });

  it("getIntegrationConfig GETs the agent integration", async () => {
    mockApiRequest.mockResolvedValue({ ok: true });

    await getIntegrationConfig("ag-1");

    expect(mockApiRequest).toHaveBeenCalledWith("GET", "genagent/agents/ag-1/integration");
  });

  it("createAgentConfig POSTs the config body", async () => {
    const body = { name: "New Agent" } as never;
    const created = { id: "created" };
    mockApiRequest.mockResolvedValue(created);

    const result = await createAgentConfig(body);

    expect(mockApiRequest).toHaveBeenCalledWith("POST", "genagent/agents/configs", body);
    expect(result).toBe(created);
  });

  it("getRagFromSchema GETs the knowledge form schema", async () => {
    mockApiRequest.mockResolvedValue({ fields: [] });

    await getRagFromSchema();

    expect(mockApiRequest).toHaveBeenCalledWith("GET", "genagent/knowledge/form_schemas");
  });

  it("updateAgentConfig strips keys outside the allowed set", async () => {
    mockApiRequest.mockResolvedValue({ id: "id-9" });

    await updateAgentConfig("id-9", {
      name: "Renamed",
      is_active: true,
      security_settings: { pci: true },
      // Disallowed keys that must be filtered out:
      id: "id-9",
      user_id: "u-1",
      created_at: "2026-01-01",
      arbitrary: "nope",
    } as never);

    expect(mockApiRequest).toHaveBeenCalledWith("PUT", "genagent/agents/configs/id-9", {
      name: "Renamed",
      is_active: true,
      security_settings: { pci: true },
    });
  });

  it("updateAgentConfig forwards every allowed key that is present", async () => {
    mockApiRequest.mockResolvedValue({ id: "id-1" });

    const full = {
      name: "n",
      description: "d",
      is_active: false,
      welcome_message: "wm",
      welcome_image: "wi",
      welcome_title: "wt",
      input_disclaimer_html: "<p>x</p>",
      possible_queries: ["q"],
      thinking_phrases: ["t"],
      thinking_phrase_delay: 3,
      greet_on_start: true,
      greeting_prompt: "gp",
      workflow_id: "wf",
      llm_analyst_id: "an",
      security_settings: { a: 1 },
    };
    await updateAgentConfig("id-1", full as never);

    expect(mockApiRequest).toHaveBeenCalledWith("PUT", "genagent/agents/configs/id-1", full);
  });

  it("updateAgentConfig sends an empty payload when no allowed keys are present", async () => {
    mockApiRequest.mockResolvedValue({});

    await updateAgentConfig("id-2", { bogus: 1 } as never);

    expect(mockApiRequest).toHaveBeenCalledWith("PUT", "genagent/agents/configs/id-2", {});
  });

  it("deleteAgentConfig DELETEs a config by id", async () => {
    mockApiRequest.mockResolvedValue({ status: "ok" });

    await deleteAgentConfig("gone");

    expect(mockApiRequest).toHaveBeenCalledWith("DELETE", "genagent/agents/configs/gone");
  });

  it("deleteWelcomeImage DELETEs the welcome image endpoint", async () => {
    const resp = { status: "ok", message: "deleted" };
    mockApiRequest.mockResolvedValue(resp);

    const result = await deleteWelcomeImage("ag-2");

    expect(mockApiRequest).toHaveBeenCalledWith(
      "DELETE",
      "genagent/agents/configs/ag-2/welcome-image"
    );
    expect(result).toBe(resp);
  });
});

describe("agent operations", () => {
  it("initializeAgent POSTs the switch endpoint with no body", async () => {
    mockApiRequest.mockResolvedValue({ ok: true });

    await initializeAgent("ag-7");

    expect(mockApiRequest).toHaveBeenCalledWith("POST", "genagent/agents/switch/ag-7");
  });

  it("queryAgent POSTs the query wrapped in a { query } body", async () => {
    mockApiRequest.mockResolvedValue({ answer: "hi" });

    await queryAgent("ag-1", "thread-2", "hello");

    expect(mockApiRequest).toHaveBeenCalledWith(
      "POST",
      "genagent/agents/ag-1/query/thread-2",
      { query: "hello" }
    );
  });
});

describe("knowledge base endpoints", () => {
  it("getAllKnowledgeItems GETs the items collection", async () => {
    mockApiRequest.mockResolvedValue([]);

    await getAllKnowledgeItems();

    expect(mockApiRequest).toHaveBeenCalledWith("GET", "genagent/knowledge/items");
  });

  it("getKnowledgeItemsList builds skip/limit with defaults", async () => {
    mockApiRequest.mockResolvedValue({ items: [] });

    await getKnowledgeItemsList();

    expect(mockApiRequest).toHaveBeenCalledWith(
      "GET",
      "genagent/knowledge/list?skip=0&limit=20"
    );
  });

  it("getKnowledgeItemsList computes skip from page and pageSize", async () => {
    mockApiRequest.mockResolvedValue({ items: [] });

    await getKnowledgeItemsList(4, 25);

    expect(mockApiRequest).toHaveBeenCalledWith(
      "GET",
      "genagent/knowledge/list?skip=75&limit=25"
    );
  });

  it("getKnowledgeItem GETs a single item by id", async () => {
    mockApiRequest.mockResolvedValue({ id: "k1" });

    await getKnowledgeItem("k1");

    expect(mockApiRequest).toHaveBeenCalledWith("GET", "genagent/knowledge/items/k1");
  });

  it("createKnowledgeItem POSTs the item body", async () => {
    const item = { name: "doc", content: "c", type: "text" };
    mockApiRequest.mockResolvedValue({ id: "k2" });

    await createKnowledgeItem(item);

    expect(mockApiRequest).toHaveBeenCalledWith("POST", "genagent/knowledge/items", item);
  });

  it("updateKnowledgeItem PUTs the item body by id", async () => {
    const item = { name: "doc", content: "c", type: "text" };
    mockApiRequest.mockResolvedValue({ id: "k3" });

    await updateKnowledgeItem("k3", item);

    expect(mockApiRequest).toHaveBeenCalledWith("PUT", "genagent/knowledge/items/k3", item);
  });

  it("deleteKnowledgeItem DELETEs an item by id", async () => {
    mockApiRequest.mockResolvedValue({ status: "ok" });

    await deleteKnowledgeItem("k4");

    expect(mockApiRequest).toHaveBeenCalledWith("DELETE", "genagent/knowledge/items/k4");
  });

  it("finalizeKnowledgeItem POSTs the finalize endpoint", async () => {
    mockApiRequest.mockResolvedValue({ status: "ok" });

    await finalizeKnowledgeItem("k5");

    expect(mockApiRequest).toHaveBeenCalledWith("POST", "genagent/knowledge/finalize/k5");
  });

  it("executeKnowledgeBaseSyncronizationManually GETs the batch task execution with kb_id", async () => {
    mockApiRequest.mockResolvedValue({ triggered: true });

    await executeKnowledgeBaseSyncronizationManually("kb-9");

    expect(mockApiRequest).toHaveBeenCalledWith(
      "GET",
      "genagent/knowledge/kb-batch-tasks-execution?kb_id=kb-9"
    );
  });
});

describe("tools endpoints", () => {
  it("getAllTools GETs the tools collection", async () => {
    mockApiRequest.mockResolvedValue([]);

    await getAllTools();

    expect(mockApiRequest).toHaveBeenCalledWith("GET", "genagent/tools");
  });

  it("getTool GETs a single tool by id", async () => {
    mockApiRequest.mockResolvedValue({ id: "t1" });

    await getTool("t1");

    expect(mockApiRequest).toHaveBeenCalledWith("GET", "genagent/tools/t1");
  });

  it("createTool POSTs the tool body", async () => {
    const tool = { name: "t", description: "d", type: "python" };
    mockApiRequest.mockResolvedValue({ id: "t2" });

    await createTool(tool);

    expect(mockApiRequest).toHaveBeenCalledWith("POST", "genagent/tools", tool);
  });

  it("updateTool PUTs the tool body by id", async () => {
    const tool = { name: "t", description: "d", type: "python" };
    mockApiRequest.mockResolvedValue({ id: "t3" });

    await updateTool("t3", tool);

    expect(mockApiRequest).toHaveBeenCalledWith("PUT", "genagent/tools/t3", tool);
  });

  it("deleteTool DELETEs a tool by id", async () => {
    mockApiRequest.mockResolvedValue({ status: "ok" });

    await deleteTool("t4");

    expect(mockApiRequest).toHaveBeenCalledWith("DELETE", "genagent/tools/t4");
  });

  it("testPythonCode POSTs code and params", async () => {
    const params = { x: 1 };
    mockApiRequest.mockResolvedValue({ result: 2 });

    await testPythonCode("print(1)", params);

    expect(mockApiRequest).toHaveBeenCalledWith("POST", "genagent/tools/python/test", {
      code: "print(1)",
      params,
    });
  });

  it("generatePythonTemplate POSTs parameters_schema", async () => {
    const schema = { type: "object", properties: {} };
    mockApiRequest.mockResolvedValue({ code: "def run(): pass" });

    await generatePythonTemplate(schema);

    expect(mockApiRequest).toHaveBeenCalledWith(
      "POST",
      "genagent/tools/python/generate-template",
      { parameters_schema: schema }
    );
  });

  it("generatePythonTemplateFromTool GETs the template-from-tool endpoint", async () => {
    mockApiRequest.mockResolvedValue({ code: "x" });

    await generatePythonTemplateFromTool("tool-9");

    expect(mockApiRequest).toHaveBeenCalledWith(
      "GET",
      "genagent/tools/python/template-from-tool/tool-9"
    );
  });

  it("testPythonCodeWithSchema POSTs code, params and parameters_schema", async () => {
    const params = { a: 1 };
    const schema = { type: "object", properties: {} };
    mockApiRequest.mockResolvedValue({ result: "ok" });

    await testPythonCodeWithSchema("code()", params, schema);

    expect(mockApiRequest).toHaveBeenCalledWith(
      "POST",
      "genagent/tools/python/test-with-schema",
      { code: "code()", params, parameters_schema: schema }
    );
  });
});

describe("getAgentIntegrationKey", () => {
  it("returns the revealed key for the agent-scoped active key", async () => {
    mockApiRequest.mockResolvedValue({ user_id: "u-1" }); // getAgentConfig
    mockGetApiKeys.mockResolvedValue([
      { id: "k-other", is_active: 1, agent_id: "different" },
      { id: "k-agent", is_active: 1, agent_id: "ag-1" },
    ] as never);
    mockRevealApiKey.mockResolvedValue({ key_val: "secret-123" } as never);

    const key = await getAgentIntegrationKey("ag-1");

    expect(mockApiRequest).toHaveBeenCalledWith("GET", "genagent/agents/configs/ag-1");
    expect(mockGetApiKeys).toHaveBeenCalledWith("u-1");
    expect(mockRevealApiKey).toHaveBeenCalledWith("k-agent");
    expect(key).toBe("secret-123");
  });

  it("falls back to any active key when none is bound to the agent", async () => {
    mockApiRequest.mockResolvedValue({ user_id: "u-2" });
    mockGetApiKeys.mockResolvedValue([
      { id: "k-inactive", is_active: 0, agent_id: "ag-1" },
      { id: "k-active", is_active: 1, agent_id: "someone-else" },
    ] as never);
    mockRevealApiKey.mockResolvedValue({ key_val: "fallback-key" } as never);

    const key = await getAgentIntegrationKey("ag-1");

    expect(mockRevealApiKey).toHaveBeenCalledWith("k-active");
    expect(key).toBe("fallback-key");
  });

  it("throws when the agent has no user_id", async () => {
    mockApiRequest.mockResolvedValue({ user_id: undefined });

    await expect(getAgentIntegrationKey("ag-1")).rejects.toThrow("Agent has no user_id");
    expect(mockGetApiKeys).not.toHaveBeenCalled();
  });

  it("throws when there is no active key", async () => {
    mockApiRequest.mockResolvedValue({ user_id: "u-3" });
    mockGetApiKeys.mockResolvedValue([{ id: "k", is_active: 0, agent_id: "ag-1" }] as never);

    await expect(getAgentIntegrationKey("ag-1")).rejects.toThrow(
      "No active API key found for this agent"
    );
    expect(mockRevealApiKey).not.toHaveBeenCalled();
  });

  it("throws when the revealed key value is missing", async () => {
    mockApiRequest.mockResolvedValue({ user_id: "u-4" });
    mockGetApiKeys.mockResolvedValue([{ id: "k", is_active: 1, agent_id: "ag-1" }] as never);
    mockRevealApiKey.mockResolvedValue({ key_val: "" } as never);

    await expect(getAgentIntegrationKey("ag-1")).rejects.toThrow("API key value missing");
  });
});
