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
  getTemplates,
  getTemplate,
  installTemplate,
  createTemplateFromAgent,
  deleteTemplate,
  publishTemplate,
  getReviewQueue,
  approveTemplate,
  rejectTemplate,
  unpublishTemplate,
  removeGlobalTemplate,
} from "@/services/templates";

const mockApiRequest = vi.mocked(apiRequest);
beforeEach(() => vi.clearAllMocks());

describe("templates service", () => {
  describe("getTemplates", () => {
    it("GETs the collection and returns the array", async () => {
      const rows = [{ id: "tpl1" }];
      mockApiRequest.mockResolvedValue(rows as never);
      const result = await getTemplates();
      expect(mockApiRequest).toHaveBeenCalledWith("GET", "genagent/templates");
      expect(result).toEqual(rows);
    });

    it("returns an empty array when the API returns a non-array", async () => {
      mockApiRequest.mockResolvedValue(null as never);
      expect(await getTemplates()).toEqual([]);
    });
  });

  it("getTemplate GETs a single template by id and passes it through", async () => {
    const tpl = { id: "tpl2" };
    mockApiRequest.mockResolvedValue(tpl as never);
    const result = await getTemplate("tpl2");
    expect(mockApiRequest).toHaveBeenCalledWith("GET", "genagent/templates/tpl2");
    expect(result).toEqual(tpl);
  });

  describe("installTemplate", () => {
    it("POSTs the provided name", async () => {
      mockApiRequest.mockResolvedValue({ id: "x" } as never);
      await installTemplate("tpl3", "Copy");
      expect(mockApiRequest).toHaveBeenCalledWith("POST", "genagent/templates/tpl3/install", {
        name: "Copy",
      });
    });

    it("defaults the name to null when omitted", async () => {
      mockApiRequest.mockResolvedValue({ id: "x" } as never);
      await installTemplate("tpl3");
      expect(mockApiRequest).toHaveBeenCalledWith("POST", "genagent/templates/tpl3/install", {
        name: null,
      });
    });

    it("throws when the API returns a falsy response", async () => {
      mockApiRequest.mockResolvedValue(null as never);
      await expect(installTemplate("tpl3")).rejects.toThrow("Failed to install template");
    });
  });

  describe("createTemplateFromAgent", () => {
    it("POSTs the payload to the from-agent endpoint", async () => {
      const payload = { agent_id: "a1" };
      const created = { id: "tpl4" };
      mockApiRequest.mockResolvedValue(created as never);
      const result = await createTemplateFromAgent(payload as never);
      expect(mockApiRequest).toHaveBeenCalledWith("POST", "genagent/templates/from-agent", payload);
      expect(result).toEqual(created);
    });

    it("throws when the API returns a falsy response", async () => {
      mockApiRequest.mockResolvedValue(null as never);
      await expect(createTemplateFromAgent({} as never)).rejects.toThrow("Failed to save template");
    });
  });

  it("deleteTemplate DELETEs by id", async () => {
    await deleteTemplate("tpl5");
    expect(mockApiRequest).toHaveBeenCalledWith("DELETE", "genagent/templates/tpl5");
  });

  describe("publishTemplate", () => {
    it("POSTs to the publish endpoint and returns the response", async () => {
      const published = { id: "tpl6" };
      mockApiRequest.mockResolvedValue(published as never);
      const result = await publishTemplate("tpl6");
      expect(mockApiRequest).toHaveBeenCalledWith("POST", "genagent/templates/tpl6/publish");
      expect(result).toEqual(published);
    });

    it("throws when the API returns a falsy response", async () => {
      mockApiRequest.mockResolvedValue(null as never);
      await expect(publishTemplate("tpl6")).rejects.toThrow("Failed to publish template");
    });
  });

  describe("getReviewQueue", () => {
    it("GETs the review queue and returns the array", async () => {
      const rows = [{ id: "tpl7" }];
      mockApiRequest.mockResolvedValue(rows as never);
      const result = await getReviewQueue();
      expect(mockApiRequest).toHaveBeenCalledWith("GET", "genagent/templates/review");
      expect(result).toEqual(rows);
    });

    it("returns an empty array when the API returns a non-array", async () => {
      mockApiRequest.mockResolvedValue(null as never);
      expect(await getReviewQueue()).toEqual([]);
    });
  });

  it("approveTemplate POSTs to the approve endpoint", async () => {
    await approveTemplate("tpl8");
    expect(mockApiRequest).toHaveBeenCalledWith("POST", "genagent/templates/review/tpl8/approve");
  });

  describe("rejectTemplate", () => {
    it("POSTs the provided reason", async () => {
      await rejectTemplate("tpl9", "spam");
      expect(mockApiRequest).toHaveBeenCalledWith("POST", "genagent/templates/review/tpl9/reject", {
        reason: "spam",
      });
    });

    it("defaults the reason to null when omitted", async () => {
      await rejectTemplate("tpl9");
      expect(mockApiRequest).toHaveBeenCalledWith("POST", "genagent/templates/review/tpl9/reject", {
        reason: null,
      });
    });
  });

  it("unpublishTemplate POSTs to the unpublish endpoint", async () => {
    await unpublishTemplate("tpl10");
    expect(mockApiRequest).toHaveBeenCalledWith("POST", "genagent/templates/tpl10/unpublish");
  });

  it("removeGlobalTemplate DELETEs from the review endpoint", async () => {
    await removeGlobalTemplate("tpl11");
    expect(mockApiRequest).toHaveBeenCalledWith("DELETE", "genagent/templates/review/tpl11");
  });
});
