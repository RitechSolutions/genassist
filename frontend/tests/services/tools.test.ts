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
  getAllTools,
  getToolById,
  createTool,
  updateTool,
  deleteTool,
  testPythonCode,
  testPythonCodeWithSchema,
  generatePythonTemplate,
} from "@/services/tools";

const mockApiRequest = vi.mocked(apiRequest);
beforeEach(() => vi.clearAllMocks());

describe("tools service", () => {
  it("getAllTools GETs the collection and passes the result through", async () => {
    const rows = [{ id: "t1" }];
    mockApiRequest.mockResolvedValue(rows as never);
    const result = await getAllTools();
    expect(mockApiRequest).toHaveBeenCalledWith("GET", "genagent/tools/");
    expect(result).toEqual(rows);
  });

  it("getToolById GETs a single tool by id", async () => {
    await getToolById("t2");
    expect(mockApiRequest).toHaveBeenCalledWith("GET", "genagent/tools/t2");
  });

  it("createTool POSTs a shallow copy of the tool", async () => {
    const tool = { name: "MyTool", description: "d" };
    await createTool(tool);
    expect(mockApiRequest).toHaveBeenCalledWith("POST", "genagent/tools/", {
      name: "MyTool",
      description: "d",
    });
    // The service spreads the tool into a new object rather than passing it by reference.
    expect(mockApiRequest.mock.calls[0][2]).not.toBe(tool);
  });

  it("updateTool PUTs the tool to the id endpoint", async () => {
    const tool = { name: "Updated" };
    await updateTool("t3", tool);
    expect(mockApiRequest).toHaveBeenCalledWith("PUT", "genagent/tools/t3", tool);
  });

  it("deleteTool DELETEs by id", async () => {
    await deleteTool("t4");
    expect(mockApiRequest).toHaveBeenCalledWith("DELETE", "genagent/tools/t4");
  });

  it("testPythonCode POSTs code and params", async () => {
    await testPythonCode("print(1)", { a: 1 });
    expect(mockApiRequest).toHaveBeenCalledWith("POST", "genagent/tools/python/test", {
      code: "print(1)",
      params: { a: 1 },
    });
  });

  it("testPythonCodeWithSchema POSTs code, params and schema", async () => {
    await testPythonCodeWithSchema("print(1)", { a: 1 }, { type: "object" });
    expect(mockApiRequest).toHaveBeenCalledWith(
      "POST",
      "genagent/tools/python/test-with-schema",
      { code: "print(1)", params: { a: 1 }, schema: { type: "object" } },
    );
  });

  it("generatePythonTemplate POSTs the schema", async () => {
    await generatePythonTemplate({ type: "object" });
    expect(mockApiRequest).toHaveBeenCalledWith(
      "POST",
      "genagent/tools/python/generate-template",
      { schema: { type: "object" } },
    );
  });
});
