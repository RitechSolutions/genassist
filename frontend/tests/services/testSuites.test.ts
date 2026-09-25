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
  listTestSuites,
  createTestSuite,
  updateTestSuite,
  deleteTestSuite,
  getTestSuite,
  listTestCases,
  addTestCase,
  updateTestCase,
  deleteTestCase,
  importCasesFromConversation,
  removeConversationFromSuite,
  listTestRunsForSuite,
  getTestRun,
  getTestRunsBatch,
  listResultsForRun,
} from "@/services/testSuites";

const mockApiRequest = vi.mocked(apiRequest);
beforeEach(() => vi.clearAllMocks());

describe("testSuites service", () => {
  it("listTestSuites GETs the suites collection and passes the result through", async () => {
    const rows = [{ id: "s1" }];
    mockApiRequest.mockResolvedValue(rows as never);
    const result = await listTestSuites();
    expect(mockApiRequest).toHaveBeenCalledWith("GET", "genagent/eval/suites");
    expect(result).toEqual(rows);
  });

  it("createTestSuite POSTs the payload to the suites collection", async () => {
    const payload = { name: "Suite" };
    await createTestSuite(payload as never);
    expect(mockApiRequest).toHaveBeenCalledWith("POST", "genagent/eval/suites", payload);
  });

  it("updateTestSuite PATCHes the payload to the suite id endpoint", async () => {
    const payload = { name: "Renamed" };
    await updateTestSuite("s2", payload as never);
    expect(mockApiRequest).toHaveBeenCalledWith("PATCH", "genagent/eval/suites/s2", payload);
  });

  it("deleteTestSuite DELETEs by suite id", async () => {
    await deleteTestSuite("s3");
    expect(mockApiRequest).toHaveBeenCalledWith("DELETE", "genagent/eval/suites/s3");
  });

  it("getTestSuite GETs a single suite by id", async () => {
    await getTestSuite("s4");
    expect(mockApiRequest).toHaveBeenCalledWith("GET", "genagent/eval/suites/s4");
  });

  it("listTestCases GETs the cases for a suite", async () => {
    await listTestCases("s5");
    expect(mockApiRequest).toHaveBeenCalledWith("GET", "genagent/eval/suites/s5/cases");
  });

  it("addTestCase POSTs the payload to the suite cases endpoint", async () => {
    const payload = { input: "hi" };
    await addTestCase("s6", payload as never);
    expect(mockApiRequest).toHaveBeenCalledWith("POST", "genagent/eval/suites/s6/cases", payload);
  });

  it("updateTestCase PATCHes the payload to the case id endpoint", async () => {
    const payload = { input: "bye" };
    await updateTestCase("c1", payload as never);
    expect(mockApiRequest).toHaveBeenCalledWith("PATCH", "genagent/eval/cases/c1", payload);
  });

  it("deleteTestCase DELETEs by case id", async () => {
    await deleteTestCase("c2");
    expect(mockApiRequest).toHaveBeenCalledWith("DELETE", "genagent/eval/cases/c2");
  });

  describe("importCasesFromConversation", () => {
    it("defaults replace to false", async () => {
      await importCasesFromConversation("s7", "conv1");
      expect(mockApiRequest).toHaveBeenCalledWith(
        "POST",
        "genagent/eval/suites/s7/cases/import-from-conversation",
        { conversation_id: "conv1", replace: false },
      );
    });

    it("passes replace=true when provided", async () => {
      await importCasesFromConversation("s7", "conv1", true);
      expect(mockApiRequest).toHaveBeenCalledWith(
        "POST",
        "genagent/eval/suites/s7/cases/import-from-conversation",
        { conversation_id: "conv1", replace: true },
      );
    });
  });

  it("removeConversationFromSuite DELETEs the conversation from the suite", async () => {
    await removeConversationFromSuite("s8", "conv2");
    expect(mockApiRequest).toHaveBeenCalledWith(
      "DELETE",
      "genagent/eval/suites/s8/conversations/conv2",
    );
  });

  it("listTestRunsForSuite GETs the runs for a suite", async () => {
    await listTestRunsForSuite("s9");
    expect(mockApiRequest).toHaveBeenCalledWith("GET", "genagent/eval/suites/s9/runs");
  });

  it("getTestRun GETs a single run by id", async () => {
    await getTestRun("run1");
    expect(mockApiRequest).toHaveBeenCalledWith("GET", "genagent/eval/runs/run1");
  });

  it("getTestRunsBatch POSTs the ids to the batch endpoint", async () => {
    await getTestRunsBatch(["r1", "r2"]);
    expect(mockApiRequest).toHaveBeenCalledWith("POST", "genagent/eval/runs/batch", {
      ids: ["r1", "r2"],
    });
  });

  it("listResultsForRun GETs the results for a run", async () => {
    await listResultsForRun("run2");
    expect(mockApiRequest).toHaveBeenCalledWith("GET", "genagent/eval/runs/run2/results");
  });
});
