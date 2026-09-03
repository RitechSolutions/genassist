import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

vi.mock("@/config/api", () => ({
  apiRequest: vi.fn(),
  getApiUrl: vi.fn(async () => "http://localhost/api/"),
  getApiUrlString: "http://localhost/api/",
  formatUploadOrNetworkError: (e: unknown) => (e instanceof Error ? e.message : String(e)),
  API_DEFAULT_TIMEOUT_MS: 1000,
  API_UPLOAD_TIMEOUT_MS: 1000,
  api: { get: vi.fn(), post: vi.fn(), put: vi.fn(), patch: vi.fn(), delete: vi.fn(), request: vi.fn() },
}));

// transcripts.ts imports getAccessToken from @/services/auth (used only by the
// skipped audio helpers). Stub it so importing the module stays side-effect free.
vi.mock("@/services/auth", () => ({
  getAccessToken: vi.fn(() => "token"),
}));

import { apiRequest } from "@/config/api";
import {
  fetchTranscripts,
  fetchConversationById,
  fetchTranscript,
  submitMessageFeedback,
  submitConversationFeedback,
  fetchAgentResponseLog,
  fetchAgentResponseLogsByConversation,
} from "@/services/transcripts";

const mockApiRequest = vi.mocked(apiRequest);
beforeEach(() => vi.clearAllMocks());

describe("fetchTranscripts", () => {
  it("builds the full query string and returns the normalized response", async () => {
    const response = {
      items: [{ id: "t1" }],
      total: 5,
      page: 2,
      page_size: 100,
      has_more: true,
    };
    mockApiRequest.mockResolvedValue(response as never);

    const result = await fetchTranscripts({
      skip: 10,
      limit: 250, // clamped to MAX_BACKEND_LIMIT (100)
      sentiment: "positive",
      hostility_neutral_max: 5,
      hostility_positive_max: 3,
      include_feedback: true,
      conversation_status: ["open", "closed"],
      order_by: "created_at",
      sort_direction: "desc",
      agent_id: "a1",
      operator_id: "op1",
      workflow_id: "w1",
      from_date: "2024-01-01",
      to_date: "2024-02-01",
      exclude_empty: true,
      id_suffix: "abcd",
      search: "hello",
      scoreFilters: { customer_satisfaction_min: 2, quality_of_service_min: undefined },
      custom_attributes: { plan: "gold" },
    });

    expect(mockApiRequest).toHaveBeenCalledWith(
      "GET",
      "conversations/?skip=10&limit=100&sentiment=positive&hostility_neutral_max=5" +
        "&hostility_positive_max=3&include_feedback=true&conversation_status=open" +
        "&conversation_status=closed&order_by=created_at&sort_direction=desc&agent_id=a1" +
        "&operator_id=op1&workflow_id=w1&from_date=2024-01-01&to_date=2024-02-01&exclude_empty=true" +
        "&id_suffix=abcd&search=hello&customer_satisfaction_min=2" +
        "&custom_attributes=%7B%22plan%22%3A%22gold%22%7D",
      undefined,
    );
    expect(result).toEqual({
      items: [{ id: "t1" }],
      total: 5,
      page: 2,
      page_size: 100,
      has_more: true,
    });
  });

  it("scopes the query to a single operator when operator_id is given", async () => {
    mockApiRequest.mockResolvedValue({ items: [] } as never);

    await fetchTranscripts({ operator_id: "op-42", limit: 1 });

    expect(mockApiRequest).toHaveBeenCalledWith(
      "GET",
      "conversations/?limit=1&operator_id=op-42",
      undefined,
    );
  });

  it("defaults limit to 20 and applies field fallbacks for a sparse response", async () => {
    mockApiRequest.mockResolvedValue({} as never);

    const result = await fetchTranscripts({});

    expect(mockApiRequest).toHaveBeenCalledWith("GET", "conversations/?limit=20", undefined);
    expect(result).toEqual({ items: [], total: 0, page: 1, page_size: 20, has_more: false });
  });

  it("returns the empty fallback object when the response is null", async () => {
    mockApiRequest.mockResolvedValue(null as never);

    const result = await fetchTranscripts({ limit: 50 });

    expect(result).toEqual({ items: [], total: 0, page: 1, page_size: 50, has_more: false });
  });

  it("returns the empty fallback object on error", async () => {
    mockApiRequest.mockRejectedValue(new Error("network"));

    const result = await fetchTranscripts({});

    expect(result).toEqual({ items: [], total: 0, page: 1, page_size: 20, has_more: false });
  });
});

describe("fetchConversationById", () => {
  it("GETs the conversation with messages included", async () => {
    const convo = { id: "c1" };
    mockApiRequest.mockResolvedValue(convo as never);

    const result = await fetchConversationById("c1");

    expect(mockApiRequest).toHaveBeenCalledWith(
      "GET",
      "conversations/c1?include_messages=true",
      undefined,
    );
    expect(result).toEqual(convo);
  });

  it("returns null when the response is null", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    await expect(fetchConversationById("c1")).resolves.toBeNull();
  });

  it("returns null on error", async () => {
    mockApiRequest.mockRejectedValue(new Error("boom"));
    await expect(fetchConversationById("c1")).resolves.toBeNull();
  });
});

describe("fetchTranscript", () => {
  it("GETs the recording by id", async () => {
    const rec = { id: "r1" };
    mockApiRequest.mockResolvedValue(rec as never);

    const result = await fetchTranscript("r1");

    expect(mockApiRequest).toHaveBeenCalledWith("GET", "audio/recordings/r1", undefined);
    expect(result).toEqual(rec);
  });

  it("returns null when the response is falsy", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    await expect(fetchTranscript("r1")).resolves.toBeNull();
  });

  it("returns null on error", async () => {
    mockApiRequest.mockRejectedValue(new Error("boom"));
    await expect(fetchTranscript("r1")).resolves.toBeNull();
  });
});

describe("submitMessageFeedback", () => {
  it("PATCHes both rating and comment when provided", async () => {
    mockApiRequest.mockResolvedValue({} as never);

    const result = await submitMessageFeedback("m1", "good", "nice work");

    expect(mockApiRequest).toHaveBeenCalledWith(
      "PATCH",
      "/conversations/message/add-feedback/m1",
      { message_id: "m1", feedback: "good", feedback_message: "nice work" },
    );
    expect(result).toBe(true);
  });

  it("omits feedback_message for a rating-only update", async () => {
    mockApiRequest.mockResolvedValue({} as never);

    await submitMessageFeedback("m1", "bad");

    expect(mockApiRequest).toHaveBeenCalledWith(
      "PATCH",
      "/conversations/message/add-feedback/m1",
      { message_id: "m1", feedback: "bad" },
    );
  });

  it("returns false on error", async () => {
    mockApiRequest.mockRejectedValue(new Error("boom"));
    await expect(submitMessageFeedback("m1", "good", "x")).resolves.toBe(false);
  });
});

describe("submitConversationFeedback", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2024-01-02T03:04:05.000Z"));
  });
  afterEach(() => vi.useRealTimers());

  it("resolves the current user id then PATCHes the feedback entry", async () => {
    mockApiRequest
      .mockResolvedValueOnce({ id: "u1" } as never)
      .mockResolvedValueOnce(undefined as never);

    const result = await submitConversationFeedback("c1", "good", "great");

    expect(mockApiRequest).toHaveBeenNthCalledWith(1, "GET", "auth/me", undefined);
    expect(mockApiRequest).toHaveBeenNthCalledWith(2, "PATCH", "/conversations/feedback/c1", {
      feedback: "good",
      feedback_message: "great",
      feedback_user_id: "u1",
      feedback_timestamp: "2024-01-02T03:04:05.000Z",
    });
    expect(result).toBe(true);
  });

  it("returns false and skips the PATCH when no user id is available", async () => {
    mockApiRequest.mockResolvedValueOnce(null as never);

    const result = await submitConversationFeedback("c1", "bad", "meh");

    expect(mockApiRequest).toHaveBeenCalledTimes(1);
    expect(result).toBe(false);
  });
});

describe("fetchAgentResponseLog", () => {
  it("GETs the agent response log for a message", async () => {
    const log = { foo: "bar" };
    mockApiRequest.mockResolvedValue(log as never);

    const result = await fetchAgentResponseLog("m1");

    expect(mockApiRequest).toHaveBeenCalledWith(
      "GET",
      "/conversations/message/agent-response-log/m1",
      undefined,
    );
    expect(result).toEqual(log);
  });

  it("returns null when the response is falsy", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    await expect(fetchAgentResponseLog("m1")).resolves.toBeNull();
  });

  it("returns null on error", async () => {
    mockApiRequest.mockRejectedValue(new Error("boom"));
    await expect(fetchAgentResponseLog("m1")).resolves.toBeNull();
  });
});

describe("fetchAgentResponseLogsByConversation", () => {
  it("GETs the agent response log summaries for a conversation", async () => {
    const logs = [{ transcript_message_id: "m1" }];
    mockApiRequest.mockResolvedValue(logs as never);

    const result = await fetchAgentResponseLogsByConversation("c1");

    expect(mockApiRequest).toHaveBeenCalledWith(
      "GET",
      "/conversations/c1/agent-response-logs",
      undefined,
    );
    expect(result).toEqual(logs);
  });

  it("returns an empty array when the response is null", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    await expect(fetchAgentResponseLogsByConversation("c1")).resolves.toEqual([]);
  });

  it("returns an empty array on error", async () => {
    mockApiRequest.mockRejectedValue(new Error("boom"));
    await expect(fetchAgentResponseLogsByConversation("c1")).resolves.toEqual([]);
  });
});
