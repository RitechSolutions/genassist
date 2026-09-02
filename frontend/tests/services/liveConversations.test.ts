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
import { conversationService } from "@/services/liveConversations";

const mockApiRequest = vi.mocked(apiRequest);
beforeEach(() => vi.clearAllMocks());

// SKIPPED: getCachedTopic / setCachedTopic / removeCachedTopic are pure localStorage
// (browser-only) accessors and are out of scope for these node tests.

describe("fetchInProgressCount", () => {
  it("requests the filter/count endpoint", async () => {
    mockApiRequest.mockResolvedValue(5 as never);
    await conversationService.fetchInProgressCount();
    expect(mockApiRequest).toHaveBeenCalledWith(
      "get",
      "/conversations/filter/count?conversation_status=takeover&conversation_status=in_progress"
    );
  });

  it("returns a plain number response as-is", async () => {
    mockApiRequest.mockResolvedValue(7 as never);
    expect(await conversationService.fetchInProgressCount()).toBe(7);
  });

  it("unwraps a { count } object response", async () => {
    mockApiRequest.mockResolvedValue({ count: 3 } as never);
    expect(await conversationService.fetchInProgressCount()).toBe(3);
  });

  it("returns 0 for null/undefined responses", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    expect(await conversationService.fetchInProgressCount()).toBe(0);
  });

  it("returns 0 for an unrecognized object shape", async () => {
    mockApiRequest.mockResolvedValue({ nope: true } as never);
    expect(await conversationService.fetchInProgressCount()).toBe(0);
  });

  it("returns 0 on rejection", async () => {
    mockApiRequest.mockRejectedValue(new Error("boom"));
    expect(await conversationService.fetchInProgressCount()).toBe(0);
  });
});

describe("fetchConversationsTranscriptsAndData", () => {
  it("requests the conversation with feedback and returns it", async () => {
    const backend = { id: "c1", duration: 10 };
    mockApiRequest.mockResolvedValue(backend as never);
    const result = await conversationService.fetchConversationsTranscriptsAndData("c1");
    expect(mockApiRequest).toHaveBeenCalledWith("get", "/conversations/c1?include_feedback=true");
    expect(result).toBe(backend);
  });

  it("throws when the conversation is not found", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    await expect(
      conversationService.fetchConversationsTranscriptsAndData("c1")
    ).rejects.toThrow("Conversation c1 not found");
  });
});

describe("fetchTranscript", () => {
  it("maps the backend transcript into the UI shape", async () => {
    const backend = {
      id: "abcd1234",
      duration: 125,
      recording: { file_path: "/audio.wav" },
      analysis: {
        neutral_sentiment: 1,
        positive_sentiment: 5,
        negative_sentiment: 2,
        tone: "happy",
        customer_satisfaction: 90,
        resolution_rate: 80,
        quality_of_service: 85,
        topic: "Billing",
      },
      agent_ratio: 60,
      customer_ratio: 40,
      word_count: 200,
      messages: [
        {
          text: "Hi",
          speaker: "Agent",
          start_time: 0,
          end_time: 1,
          create_time: "2025-01-01T00:00:00Z",
          type: "message",
          id: "m1",
          feedback: [],
        },
      ],
    };
    mockApiRequest.mockResolvedValue(backend as never);

    const result = await conversationService.fetchTranscript("abcd1234");

    expect(mockApiRequest).toHaveBeenCalledWith("get", "/conversations/abcd1234");
    expect(result).toEqual({
      id: "abcd1234",
      audio: "/audio.wav",
      duration: "2m 5s",
      metadata: {
        isCall: true,
        duration: "2m 5s",
        title: "Call #1234",
        topic: "Billing",
      },
      transcript: [
        {
          text: "Hi",
          speaker: "Agent",
          start_time: 0,
          end_time: 1,
          create_time: "2025-01-01T00:00:00Z",
          type: "message",
          message_id: "m1",
          feedback: [],
        },
      ],
      metrics: {
        sentiment: "positive",
        customerSatisfaction: 90,
        serviceQuality: 85,
        resolutionRate: 80,
        speakingRatio: { agent: 60, customer: 40 },
        tone: ["happy"],
        wordCount: 200,
      },
    });
  });

  it("derives a negative dominant sentiment and defaults for missing fields", async () => {
    const backend = {
      id: "0000zzzz",
      duration: 30,
      analysis: {
        neutral_sentiment: 1,
        positive_sentiment: 0,
        negative_sentiment: 9,
        tone: "angry",
      },
      messages: [],
    };
    mockApiRequest.mockResolvedValue(backend as never);

    const result = await conversationService.fetchTranscript("0000zzzz");
    expect(result.metrics.sentiment).toBe("negative");
    expect(result.audio).toBe("");
    expect(result.metadata.isCall).toBe(false);
    expect(result.duration).toBe("0m 30s");
    expect(result.metrics.speakingRatio).toEqual({ agent: 50, customer: 50 });
  });
});

describe("fetchActive", () => {
  it("requests the base params and normalizes/filters the list", async () => {
    const rec1 = {
      id: "c1",
      status: "in_progress",
      recording: null,
      created_at: "2025-01-01T00:00:00Z",
      in_progress_hostility_score: 3,
      duration: 60,
      word_count: 100,
      agent_ratio: 50,
      customer_ratio: 50,
      supervisor_id: "s1",
      analysis: { topic: "Support" },
      messages: [],
    };
    const rec2 = { id: "c2", status: "completed", messages: [] };
    mockApiRequest.mockResolvedValue({ items: [rec1, rec2] } as never);

    const result = await conversationService.fetchActive();

    expect(mockApiRequest).toHaveBeenCalledWith(
      "get",
      "/conversations/?skip=0&limit=3&conversation_status=in_progress&conversation_status=takeover"
    );
    expect(result.total).toBe(1);
    expect(result.conversations).toHaveLength(1);
    expect(result.conversations[0]).toMatchObject({
      id: "c1",
      type: "chat",
      status: "in-progress",
      sentiment: "negative",
      timestamp: "2025-01-01T00:00:00Z",
      in_progress_hostility_score: 3,
      supervisor_id: "s1",
      topic: "Support",
    });
  });

  it("appends sentiment and hostility params when a sentiment filter is set", async () => {
    mockApiRequest.mockResolvedValue([] as never);
    await conversationService.fetchActive({
      sentiment: "Negative",
      hostility_neutral_max: 5,
      hostility_positive_max: 7,
    });
    expect(mockApiRequest).toHaveBeenCalledWith(
      "get",
      "/conversations/?skip=0&limit=3&conversation_status=in_progress&conversation_status=takeover&sentiment=negative&hostility_neutral_max=5&hostility_positive_max=7"
    );
  });

  it("returns an empty result on rejection", async () => {
    mockApiRequest.mockRejectedValue(new Error("boom"));
    expect(await conversationService.fetchActive()).toEqual({ total: 0, conversations: [] });
  });
});

describe("takeoverConversation", () => {
  it("patches the takeover endpoint and returns true", async () => {
    mockApiRequest.mockResolvedValue(undefined as never);
    const result = await conversationService.takeoverConversation("id1");
    expect(mockApiRequest).toHaveBeenCalledWith(
      "patch",
      "conversations/in-progress/takeover-super/id1"
    );
    expect(result).toBe(true);
  });

  it("returns false on rejection", async () => {
    mockApiRequest.mockRejectedValue(new Error("boom"));
    expect(await conversationService.takeoverConversation("id1")).toBe(false);
  });
});

describe("updateConversation", () => {
  it("patches the update endpoint with the provided data", async () => {
    mockApiRequest.mockResolvedValue(undefined as never);
    const data = { messages: [], llm_analyst_id: "an1" };
    await conversationService.updateConversation("id1", data as never);
    expect(mockApiRequest).toHaveBeenCalledWith(
      "patch",
      "/conversations/in-progress/update/id1",
      data
    );
  });
});

describe("finalizeConversation", () => {
  it("patches the finalize endpoint with an empty body", async () => {
    mockApiRequest.mockResolvedValue(undefined as never);
    await conversationService.finalizeConversation("id1");
    expect(mockApiRequest).toHaveBeenCalledWith(
      "patch",
      "/conversations/in-progress/finalize/id1",
      {}
    );
  });
});

describe("getCachedTranscript", () => {
  it("always returns null", () => {
    expect(conversationService.getCachedTranscript("id1")).toBeNull();
  });
});
