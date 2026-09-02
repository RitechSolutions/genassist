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
import { askAIQuestion } from "@/services/aiChat";

const mockApiRequest = vi.mocked(apiRequest);
beforeEach(() => vi.clearAllMocks());

const FALLBACK = { answer: "Sorry, I couldn't process your request." };

describe("askAIQuestion", () => {
  it("POSTs the question and returns the answer", async () => {
    const answer = { answer: "42" };
    mockApiRequest.mockResolvedValue(answer as never);

    const result = await askAIQuestion("c1", "what is it?");

    expect(mockApiRequest).toHaveBeenCalledWith("post", "/audio/ask_question", {
      conversation_id: "c1",
      question: "what is it?",
    });
    expect(result).toEqual(answer);
  });

  it("returns the fallback answer when the response is null", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    await expect(askAIQuestion("c1", "q")).resolves.toEqual(FALLBACK);
  });

  it("returns the fallback answer on error", async () => {
    mockApiRequest.mockRejectedValue(new Error("boom"));
    await expect(askAIQuestion("c1", "q")).resolves.toEqual(FALLBACK);
  });
});
