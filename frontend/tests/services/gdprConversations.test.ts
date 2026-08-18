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
  searchConversationsByEmail,
  deleteConversationForGdpr,
} from "@/services/gdprConversations";

const mockApiRequest = vi.mocked(apiRequest);
beforeEach(() => vi.clearAllMocks());

describe("searchConversationsByEmail", () => {
  it("builds the query string with defaults and returns the response", async () => {
    const response = {
      items: [{ id: "c1" }],
      total: 1,
      page: 1,
      page_size: 20,
      has_more: false,
    };
    mockApiRequest.mockResolvedValue(response as never);
    const result = await searchConversationsByEmail("user@example.com");
    expect(mockApiRequest).toHaveBeenCalledWith(
      "GET",
      "/conversations?email=user%40example.com&skip=0&limit=20&include_messages=false"
    );
    expect(result).toBe(response);
  });

  it("threads skip/limit options into the query string", async () => {
    mockApiRequest.mockResolvedValue({
      items: [],
      total: 0,
      page: 1,
      page_size: 50,
      has_more: false,
    } as never);
    await searchConversationsByEmail("user@example.com", { skip: 5, limit: 50 });
    expect(mockApiRequest).toHaveBeenCalledWith(
      "GET",
      "/conversations?email=user%40example.com&skip=5&limit=50&include_messages=false"
    );
  });

  it("returns an empty fallback when apiRequest resolves null", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    const result = await searchConversationsByEmail("user@example.com", { limit: 50 });
    expect(result).toEqual({
      items: [],
      total: 0,
      page: 1,
      page_size: 50,
      has_more: false,
    });
  });

  it("uses page_size 20 in the fallback when no limit is given", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    const result = await searchConversationsByEmail("user@example.com");
    expect(result.page_size).toBe(20);
  });
});

describe("deleteConversationForGdpr", () => {
  it("deletes with the encoded mode query param", async () => {
    mockApiRequest.mockResolvedValue(undefined as never);
    await deleteConversationForGdpr("c1", "hard");
    expect(mockApiRequest).toHaveBeenCalledWith("DELETE", "/conversations/c1/gdpr?mode=hard");
  });

  it("passes the anonymize mode through", async () => {
    mockApiRequest.mockResolvedValue(undefined as never);
    await deleteConversationForGdpr("c2", "anonymize");
    expect(mockApiRequest).toHaveBeenCalledWith("DELETE", "/conversations/c2/gdpr?mode=anonymize");
  });
});
