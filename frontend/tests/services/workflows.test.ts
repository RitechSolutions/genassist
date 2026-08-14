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
  getAllWorkflows,
  getWorkflowsMinimal,
  getWorkflowSummaries,
  getWorkflowById,
  createWorkflow,
  updateWorkflow,
  deleteWorkflow,
  getAllNodeSchemas,
  testNode,
  testWorkflow,
  generatePythonTemplate,
  createWorkflowFromWizard,
  createWorkflowFromBuilder,
} from "@/services/workflows";

const mockApiRequest = vi.mocked(apiRequest);
beforeEach(() => vi.clearAllMocks());

describe("workflows service", () => {
  it("getAllWorkflows GETs the collection and passes the result through", async () => {
    const rows = [{ id: "w1" }];
    mockApiRequest.mockResolvedValue(rows as never);
    const result = await getAllWorkflows();
    expect(mockApiRequest).toHaveBeenCalledWith("GET", "genagent/workflow/");
    expect(result).toEqual(rows);
  });

  it("getWorkflowsMinimal GETs the minimal list", async () => {
    await getWorkflowsMinimal();
    expect(mockApiRequest).toHaveBeenCalledWith("GET", "genagent/workflow/minimal");
  });

  it("getWorkflowSummaries encodes the agent_id query parameter", async () => {
    await getWorkflowSummaries("a b/c&d");
    expect(mockApiRequest).toHaveBeenCalledWith(
      "GET",
      "genagent/workflow/summaries?agent_id=a%20b%2Fc%26d",
    );
  });

  it("getWorkflowById GETs a single workflow by id", async () => {
    await getWorkflowById("wf-1");
    expect(mockApiRequest).toHaveBeenCalledWith("GET", "genagent/workflow/wf-1");
  });

  it("createWorkflow POSTs the payload to the collection", async () => {
    const payload = { name: "New" };
    await createWorkflow(payload as never);
    expect(mockApiRequest).toHaveBeenCalledWith("POST", "genagent/workflow/", payload);
  });

  it("updateWorkflow PUTs the payload to the id endpoint", async () => {
    const payload = { name: "Renamed" };
    await updateWorkflow("wf-2", payload as never);
    expect(mockApiRequest).toHaveBeenCalledWith("PUT", "genagent/workflow/wf-2", payload);
  });

  it("deleteWorkflow DELETEs by id", async () => {
    await deleteWorkflow("wf-3");
    expect(mockApiRequest).toHaveBeenCalledWith("DELETE", "genagent/workflow/wf-3");
  });

  it("getAllNodeSchemas GETs the schemas and returns them", async () => {
    const schemas = { agentNode: [] };
    mockApiRequest.mockResolvedValue(schemas as never);
    const result = await getAllNodeSchemas();
    expect(mockApiRequest).toHaveBeenCalledWith("GET", "genagent/workflow/node_schemas");
    expect(result).toEqual(schemas);
  });

  it("getAllNodeSchemas rethrows and logs on failure", async () => {
    const errorSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    mockApiRequest.mockRejectedValueOnce(new Error("boom"));
    await expect(getAllNodeSchemas()).rejects.toThrow("boom");
    expect(errorSpy).toHaveBeenCalled();
    errorSpy.mockRestore();
  });

  it("testNode POSTs the node test payload", async () => {
    const payload = { input_data: {}, node_type: "agent", node_config: {} };
    await testNode(payload as never);
    expect(mockApiRequest).toHaveBeenCalledWith("POST", "genagent/workflow/test-node", payload);
  });

  it("testWorkflow POSTs the workflow test payload", async () => {
    const payload = { input_data: {}, workflow: { id: "w" } };
    await testWorkflow(payload as never);
    expect(mockApiRequest).toHaveBeenCalledWith("POST", "genagent/workflow/test", payload);
  });

  it("generatePythonTemplate POSTs schema and prompt", async () => {
    const schema = { type: "object" };
    await generatePythonTemplate(schema, "do it");
    expect(mockApiRequest).toHaveBeenCalledWith(
      "POST",
      "genagent/workflow/generate-python-template",
      { parameters_schema: schema, prompt: "do it" },
    );
  });

  it("generatePythonTemplate sends an undefined prompt when omitted", async () => {
    const schema = { type: "object" };
    await generatePythonTemplate(schema);
    expect(mockApiRequest).toHaveBeenCalledWith(
      "POST",
      "genagent/workflow/generate-python-template",
      { parameters_schema: schema, prompt: undefined },
    );
  });

  it("createWorkflowFromWizard POSTs to the wizard endpoint", async () => {
    const payload = { workflow_name: "W", workflow_json: "{}" };
    await createWorkflowFromWizard(payload);
    expect(mockApiRequest).toHaveBeenCalledWith(
      "POST",
      "workflow-manager/config/from-wizard",
      payload,
    );
  });

  it("createWorkflowFromBuilder POSTs to the builder endpoint", async () => {
    const payload = { workflow_name: "W", workflow_json: "{}" };
    await createWorkflowFromBuilder(payload);
    expect(mockApiRequest).toHaveBeenCalledWith(
      "POST",
      "workflow-builder/config/from-builder",
      payload,
    );
  });
});
