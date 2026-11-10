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
import { getBuilderDraft, getBuilderTools } from "@/services/workflowBuilder";

const mockApiRequest = vi.mocked(apiRequest);
beforeEach(() => vi.clearAllMocks());

describe("workflowBuilder service", () => {
  it("lists the builder tool set the canvas describes the tools node with", async () => {
    const tools = [{ name: "apply_plan", description: "Apply a plan" }];
    mockApiRequest.mockResolvedValue(tools as never);

    expect(await getBuilderTools()).toEqual(tools);
    expect(mockApiRequest).toHaveBeenCalledWith("GET", "workflow-builder/tools");
  });

  it("reads a conversation's draft by id", async () => {
    mockApiRequest.mockResolvedValue({ nodes: [], edges: [] } as never);

    await getBuilderDraft("conv-1");
    expect(mockApiRequest).toHaveBeenCalledWith("GET", "workflow-builder/drafts/conv-1");
  });
});
