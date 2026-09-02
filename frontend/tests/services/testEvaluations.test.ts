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
  listTestEvaluations,
  getTestEvaluationById,
  createTestEvaluation,
  updateTestEvaluation,
  deleteTestEvaluation,
  runTestEvaluation,
  runWorkflowEvaluations,
  getWorkflowEvaluationSummaries,
  getWorkflowEvaluationsPage,
  getEvaluationToolCatalog,
  getToolRuleResults,
  exportTestEvaluation,
  previewEvaluationImport,
  importEvaluation,
  exportWorkflowEvaluations,
  previewEvaluationSetImport,
  importEvaluationSet,
} from "@/services/testEvaluations";

const mockApiRequest = vi.mocked(apiRequest);
beforeEach(() => vi.clearAllMocks());

describe("testEvaluations service", () => {
  it("listTestEvaluations GETs the evaluations collection", async () => {
    const rows = [{ id: "e1" }];
    mockApiRequest.mockResolvedValue(rows as never);
    const result = await listTestEvaluations();
    expect(mockApiRequest).toHaveBeenCalledWith("GET", "genagent/eval/evaluations");
    expect(result).toEqual(rows);
  });

  it("getTestEvaluationById GETs a single evaluation by id", async () => {
    await getTestEvaluationById("e2");
    expect(mockApiRequest).toHaveBeenCalledWith("GET", "genagent/eval/evaluations/e2");
  });

  it("createTestEvaluation POSTs the payload to the evaluations collection", async () => {
    const payload = { name: "Eval" };
    await createTestEvaluation(payload as never);
    expect(mockApiRequest).toHaveBeenCalledWith("POST", "genagent/eval/evaluations", payload);
  });

  it("updateTestEvaluation PATCHes the payload to the evaluation id endpoint", async () => {
    const payload = { name: "Renamed" };
    await updateTestEvaluation("e3", payload as never);
    expect(mockApiRequest).toHaveBeenCalledWith("PATCH", "genagent/eval/evaluations/e3", payload);
  });

  it("deleteTestEvaluation DELETEs by id", async () => {
    await deleteTestEvaluation("e4");
    expect(mockApiRequest).toHaveBeenCalledWith("DELETE", "genagent/eval/evaluations/e4");
  });

  describe("runTestEvaluation", () => {
    it("POSTs the target workflow id when provided", async () => {
      await runTestEvaluation("e5", "wf-1");
      expect(mockApiRequest).toHaveBeenCalledWith("POST", "genagent/eval/evaluations/e5/run", {
        target_workflow_id: "wf-1",
      });
    });

    it("POSTs an empty object when no target workflow id is provided", async () => {
      await runTestEvaluation("e5");
      expect(mockApiRequest).toHaveBeenCalledWith("POST", "genagent/eval/evaluations/e5/run", {});
    });
  });

  describe("runWorkflowEvaluations", () => {
    it("POSTs the target workflow id when provided", async () => {
      await runWorkflowEvaluations("wf-2", "wf-target");
      expect(mockApiRequest).toHaveBeenCalledWith(
        "POST",
        "genagent/eval/workflows/wf-2/evaluations/run",
        { target_workflow_id: "wf-target" },
      );
    });

    it("POSTs undefined body when no target workflow id is provided", async () => {
      await runWorkflowEvaluations("wf-2");
      expect(mockApiRequest).toHaveBeenCalledWith(
        "POST",
        "genagent/eval/workflows/wf-2/evaluations/run",
        undefined,
      );
    });
  });

  it("getWorkflowEvaluationSummaries GETs the summaries endpoint", async () => {
    await getWorkflowEvaluationSummaries();
    expect(mockApiRequest).toHaveBeenCalledWith(
      "GET",
      "genagent/eval/workflows/evaluation-summaries",
    );
  });

  describe("getWorkflowEvaluationsPage", () => {
    it("builds the page and page_size query without search", async () => {
      await getWorkflowEvaluationsPage("wf-3", { page: 2, pageSize: 20 });
      expect(mockApiRequest).toHaveBeenCalledWith(
        "GET",
        "genagent/eval/workflows/wf-3/evaluations?page=2&page_size=20",
      );
    });

    it("appends a trimmed search term when provided", async () => {
      await getWorkflowEvaluationsPage("wf-3", { page: 1, pageSize: 10, search: "  hello  " });
      expect(mockApiRequest).toHaveBeenCalledWith(
        "GET",
        "genagent/eval/workflows/wf-3/evaluations?page=1&page_size=10&search=hello",
      );
    });

    it("omits a whitespace-only search term", async () => {
      await getWorkflowEvaluationsPage("wf-3", { page: 1, pageSize: 10, search: "   " });
      expect(mockApiRequest).toHaveBeenCalledWith(
        "GET",
        "genagent/eval/workflows/wf-3/evaluations?page=1&page_size=10",
      );
    });
  });

  it("getEvaluationToolCatalog GETs the tool catalog for a workflow", async () => {
    await getEvaluationToolCatalog("wf-4");
    expect(mockApiRequest).toHaveBeenCalledWith(
      "GET",
      "genagent/eval/workflows/wf-4/evaluation-tool-catalog",
    );
  });

  it("getToolRuleResults GETs the tool-rule-results for a run", async () => {
    await getToolRuleResults("run1");
    expect(mockApiRequest).toHaveBeenCalledWith(
      "GET",
      "genagent/eval/runs/run1/tool-rule-results",
    );
  });

  it("exportTestEvaluation GETs the export endpoint for an evaluation", async () => {
    await exportTestEvaluation("e6");
    expect(mockApiRequest).toHaveBeenCalledWith("GET", "genagent/eval/evaluations/e6/export");
  });

  it("previewEvaluationImport POSTs the payload to the import preview endpoint", async () => {
    const payload = { bundle: { k: 1 }, target_workflow_id: "wf-5" };
    await previewEvaluationImport(payload as never);
    expect(mockApiRequest).toHaveBeenCalledWith(
      "POST",
      "genagent/eval/evaluations/import/preview",
      payload,
    );
  });

  it("importEvaluation POSTs the payload to the import endpoint", async () => {
    const payload = { bundle: { k: 1 }, target_workflow_id: "wf-5" };
    await importEvaluation(payload as never);
    expect(mockApiRequest).toHaveBeenCalledWith(
      "POST",
      "genagent/eval/evaluations/import",
      payload,
    );
  });

  it("exportWorkflowEvaluations GETs the workflow evaluations export endpoint", async () => {
    await exportWorkflowEvaluations("wf-6");
    expect(mockApiRequest).toHaveBeenCalledWith(
      "GET",
      "genagent/eval/workflows/wf-6/evaluations/export",
    );
  });

  it("previewEvaluationSetImport POSTs the payload to the import-set preview endpoint", async () => {
    const payload = { bundle_set: { k: 1 }, target_workflow_id: "wf-7" };
    await previewEvaluationSetImport(payload as never);
    expect(mockApiRequest).toHaveBeenCalledWith(
      "POST",
      "genagent/eval/evaluations/import-set/preview",
      payload,
    );
  });

  it("importEvaluationSet POSTs the payload to the import-set endpoint", async () => {
    const payload = { bundle_set: { k: 1 }, target_workflow_id: "wf-7" };
    await importEvaluationSet(payload as never);
    expect(mockApiRequest).toHaveBeenCalledWith(
      "POST",
      "genagent/eval/evaluations/import-set",
      payload,
    );
  });
});
