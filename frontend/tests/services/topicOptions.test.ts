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
import { fetchTopicOptions } from "@/services/topicOptions";

const mockApiRequest = vi.mocked(apiRequest);
beforeEach(() => vi.clearAllMocks());

describe("fetchTopicOptions", () => {
  it("GETs the topic options and unwraps the topics list", async () => {
    const topics = [{ name: "Refund", subtopics: ["Wrong plate"] }];
    mockApiRequest.mockResolvedValue({ topics } as never);
    expect(await fetchTopicOptions()).toBe(topics);
    expect(mockApiRequest).toHaveBeenCalledWith("GET", "conversations/topic-options");
  });

  it("returns [] when the response is null", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    expect(await fetchTopicOptions()).toEqual([]);
  });
});
