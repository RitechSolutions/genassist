import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("@/config/api", () => ({
  apiRequest: vi.fn(),
  getApiUrl: vi.fn(async () => "http://localhost/api/"),
  getApiUrlString: "http://localhost/api/",
  formatUploadOrNetworkError: (e: unknown) => (e instanceof Error ? e.message : String(e)),
  API_DEFAULT_TIMEOUT_MS: 1000,
  API_UPLOAD_TIMEOUT_MS: 1000,
  API_WORKFLOW_TEST_TIMEOUT_MS: 1000,
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
  getFailedNodeDisplayMessage,
  getTrainDataSourceTestFailureMessage,
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
    expect(mockApiRequest).toHaveBeenCalledWith("POST", "genagent/workflow/test-node", payload, {
      timeout: 1000,
    });
  });

  it("testWorkflow POSTs the workflow test payload", async () => {
    const payload = { input_data: {}, workflow: { id: "w" } };
    await testWorkflow(payload as never);
    expect(mockApiRequest).toHaveBeenCalledWith("POST", "genagent/workflow/test", payload, {
      timeout: 1000,
    });
  });

  describe("getTrainDataSourceTestFailureMessage", () => {
    it("returns the client-safe Train Data Source failure without the engine prefix", () => {
      const response = {
        status: "success",
        input: "",
        output: "",
        has_failures: true,
        failed_nodes: [
          {
            node_id: "test-trainDataSourceNode-1",
            name: "Train Data Source",
            type: "trainDataSourceNode",
            error:
              "Error executing node test-trainDataSourceNode-1: The query returned more than 2,000,000 rows, which exceeds the limit of 2,000,000. Add a filter or LIMIT, or ask an administrator to raise the row limit.",
          },
        ],
      };

      expect(getTrainDataSourceTestFailureMessage(response)).toBe(
        "The query returned more than 2,000,000 rows, which exceeds the limit of 2,000,000. Add a filter or LIMIT, or ask an administrator to raise the row limit."
      );
    });

    it("ignores failed nodes of other types", () => {
      const response = {
        status: "success",
        input: "",
        output: "",
        has_failures: true,
        failed_nodes: [
          {
            node_id: "test-agentNode-1",
            name: "Agent",
            type: "agentNode",
            error: "Error executing node test-agentNode-1: Agent failed.",
          },
        ],
      };

      expect(getTrainDataSourceTestFailureMessage(response)).toBeNull();
    });

    it("uses safe guidance when a Train Data Source failure has no message", () => {
      const response = {
        status: "success",
        input: "",
        output: "",
        has_failures: true,
        failed_nodes: [
          {
            node_id: "test-trainDataSourceNode-1",
            name: "Train Data Source",
            type: "trainDataSourceNode",
            error: "",
          },
        ],
      };

      expect(getTrainDataSourceTestFailureMessage(response)).toBe(
        "Train Data Source could not complete the test. Check its configuration and try again."
      );
    });

    it("formats Train Data Source errors for the full workflow panel", () => {
      expect(
        getFailedNodeDisplayMessage({
          node_id: "source-1",
          name: "Train Data Source",
          type: "trainDataSourceNode",
          error: "Error executing node source-1: Enter a SQL query.",
        })
      ).toBe("Enter a SQL query.");
    });

    it("does not change errors for other node types", () => {
      const error = "Error executing node agent-1: Upstream failed.";
      expect(
        getFailedNodeDisplayMessage({
          node_id: "agent-1",
          name: "Agent",
          type: "agentNode",
          error,
        })
      ).toBe(error);
    });

    it("returns null when the response contains no Train Data Source failure", () => {
      expect(
        getTrainDataSourceTestFailureMessage({
          status: "success",
          input: "",
          output: "ok",
          has_failures: false,
          failed_nodes: [],
        })
      ).toBeNull();
      expect(getTrainDataSourceTestFailureMessage(null)).toBeNull();
    });
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
