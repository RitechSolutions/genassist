import { describe, expect, it, vi } from "vitest";

// transformers.ts has a top-level `await getApiUrl()` and imports @/config/api,
// so we stub the config module to keep the import pure and deterministic.
vi.mock("@/config/api", () => ({
  getApiUrlString: "http://localhost/api/",
  getApiUrl: async () => "http://localhost/api/",
  apiRequest: async () => null,
  api: {},
}));

import {
  processApiResponse,
  transformTranscript,
} from "@/views/Transcripts/helpers/transformers";
import type { BackendTranscript } from "@/interfaces/transcript.interface";

const asBackend = (value: unknown): BackendTranscript => value as BackendTranscript;

describe("processApiResponse", () => {
  it("returns an empty array for falsy input", () => {
    expect(processApiResponse(null)).toEqual([]);
    expect(processApiResponse(undefined)).toEqual([]);
    expect(processApiResponse("")).toEqual([]);
    expect(processApiResponse(0)).toEqual([]);
  });

  it("returns an empty array for a truthy non-array, non-object value", () => {
    expect(processApiResponse(5)).toEqual([]);
    expect(processApiResponse("hello")).toEqual([]);
  });

  it("maps an array, setting isCall from the recording field", () => {
    const result = processApiResponse([
      { recording: { file_path: "/a" } },
      { recording: null },
    ]);
    expect(result).toEqual([
      { recording: { file_path: "/a" }, isCall: true },
      { recording: null, isCall: false },
    ]);
  });

  it("unwraps an object with a data array", () => {
    expect(processApiResponse({ data: [{ recording: 1 }] })).toEqual([
      { recording: 1, isCall: true },
    ]);
  });

  it("unwraps an object with a recordings array", () => {
    expect(processApiResponse({ recordings: [{}] })).toEqual([
      { isCall: false },
    ]);
  });

  it("prefers data over recordings when both are arrays", () => {
    expect(
      processApiResponse({
        data: [{ recording: 1 }],
        recordings: [{ recording: 2 }],
      })
    ).toEqual([{ recording: 1, isCall: true }]);
  });

  it("wraps a plain object as a single-element array", () => {
    expect(processApiResponse({ recording: { x: 1 }, foo: 2 })).toEqual([
      { recording: { x: 1 }, foo: 2, isCall: true },
    ]);
  });

  it("wraps an object whose data field is not an array", () => {
    expect(processApiResponse({ data: "nope" })).toEqual([
      { data: "nope", isCall: false },
    ]);
  });
});

describe("transformTranscript - error handling", () => {
  it("returns the error fallback object when backendData is null", () => {
    const result = transformTranscript(asBackend(null));
    expect(result.id).toBe("error");
    expect(result.metadata.title).toBe("Error");
    expect(result.metadata.topic).toBe(" - Unknown");
    expect(result.metadata.isCall).toBe(false);
    expect(result.metrics.sentiment).toBe("neutral");
    expect(result.transcription).toEqual([]);
    expect(result.messages).toEqual([]);
  });

  it("returns the error fallback when the id is missing (id.toString throws)", () => {
    const result = transformTranscript(asBackend({}));
    expect(result.id).toBe("error");
    expect(result.status).toBe("unknown");
  });
});

describe("transformTranscript - minimal input", () => {
  const result = transformTranscript(asBackend({ id: 1 }));

  it("stringifies the id and applies default scalars", () => {
    expect(result.id).toBe("1");
    expect(result.agent_id).toBeNull();
    expect(result.agent_name).toBeNull();
    expect(result.audio).toBe("");
    expect(result.status).toBe("unknown");
    expect(result.supervisor_username).toBeNull();
    expect(result.thumbs_up_count).toBe(0);
    expect(result.thumbs_down_count).toBe(0);
    expect(result.custom_attributes).toBeNull();
    expect(result.duration).toBe(0);
  });

  it("builds default metadata and metrics", () => {
    expect(result.metadata).toEqual({
      isCall: false,
      duration: 0,
      title: "Conversation 1",
      topic: "Unknown",
    });
    expect(result.metrics.sentiment).toBe("neutral");
    expect(result.metrics.tone).toEqual(["neutral"]);
    expect(result.metrics.speakingRatio).toEqual({ agent: 50, customer: 50 });
    expect(result.metrics.wordCount).toBe(0);
    expect(result.transcription).toEqual([]);
  });

  it("uses ISO-string timestamps by default", () => {
    expect(typeof result.create_time).toBe("string");
    expect(typeof result.timestamp).toBe("string");
  });
});

describe("transformTranscript - rich input with messages", () => {
  const result = transformTranscript(
    asBackend({
      id: 42,
      recording: { file_path: "/audio/x.mp3" },
      recording_id: "rec1",
      created_at: "2020-01-01T00:00:00Z",
      duration: 125,
      status: "finalized",
      agent_id: 7,
      agent_name: "Bot",
      agent_ratio: 60,
      customer_ratio: 40,
      word_count: 100,
      in_progress_hostility_score: 30,
      supervisor_id: "sup1",
      supervisor_username: "sup",
      analysis: {
        positive_sentiment: 5,
        negative_sentiment: 1,
        neutral_sentiment: 2,
        tone: "happy",
        topic: "Billing",
        customer_satisfaction: 4,
        quality_of_service: 3,
        resolution_rate: 0.9,
        efficiency: 0.8,
      },
      messages: [
        {
          speaker: "Agent",
          start_time: 0,
          end_time: 2,
          text: "Hello",
          id: "m1",
          type: "message",
        },
        {
          speaker: "Customer",
          start_time: 5,
          text: "Hi",
          feedback: '[{"feedback":"good"}]',
        },
      ],
      feedback: '[{"feedback":"bad","feedback_timestamp":"t"}]',
      thumbs_up_count: 3,
      thumbs_down_count: 1,
      custom_attributes: { plan: "pro" },
    })
  );

  it("marks it as a call and builds the audio URL from the mocked base url", () => {
    expect(result.metadata.isCall).toBe(true);
    expect(result.audio).toBe("http://localhost/api//audio/x.mp3");
  });

  it("converts a numeric agent_id to a string and passes through scalars", () => {
    expect(result.id).toBe("42");
    expect(result.agent_id).toBe("7");
    expect(result.agent_name).toBe("Bot");
    expect(result.recording_id).toBe("rec1");
    expect(result.status).toBe("finalized");
    expect(result.duration).toBe(125);
    expect(result.supervisor_id).toBe("sup1");
    expect(result.supervisor_username).toBe("sup");
    expect(result.thumbs_up_count).toBe(3);
    expect(result.thumbs_down_count).toBe(1);
    expect(result.custom_attributes).toEqual({ plan: "pro" });
  });

  it("picks the dominant (positive) sentiment and maps analysis metrics", () => {
    expect(result.metrics.sentiment).toBe("positive");
    expect(result.metrics.customerSatisfaction).toBe(4);
    expect(result.metrics.serviceQuality).toBe(3);
    expect(result.metrics.resolutionRate).toBe(0.9);
    expect(result.metrics.efficiency).toBe(0.8);
    expect(result.metrics.tone).toEqual(["happy"]);
    expect(result.metrics.speakingRatio).toEqual({ agent: 60, customer: 40 });
    expect(result.metrics.wordCount).toBe(100);
    expect(result.metrics.in_progress_hostility_score).toBe(30);
    expect(result.metadata.topic).toBe("Billing");
  });

  it("maps messages, filling defaults and parsing per-message feedback", () => {
    expect(result.messages).toHaveLength(2);
    const [first, second] = result.messages!;
    expect(first.speaker).toBe("Agent");
    expect(first.text).toBe("Hello");
    expect(first.end_time).toBe(2);
    expect(first.message_id).toBe("m1");
    expect(first.type).toBe("message");
    expect(first.feedback).toBeUndefined();

    // end_time defaults to start_time + 0.01 when missing.
    expect(second.speaker).toBe("Customer");
    expect(second.end_time).toBeCloseTo(5.01);
    expect(second.message_id).toBeUndefined();
    expect(second.feedback).toEqual([{ feedback: "good" }]);
  });

  it("parses the conversation-level feedback JSON string", () => {
    expect(result.feedback).toEqual([
      { feedback: "bad", feedback_timestamp: "t" },
    ]);
  });
});

describe("transformTranscript - dominant negative sentiment", () => {
  it("selects negative when it strictly exceeds the others", () => {
    const result = transformTranscript(
      asBackend({
        id: 3,
        analysis: {
          positive_sentiment: 1,
          negative_sentiment: 9,
          neutral_sentiment: 2,
        },
      })
    );
    expect(result.metrics.sentiment).toBe("negative");
  });

  it("stays neutral on a tie", () => {
    const result = transformTranscript(
      asBackend({
        id: 4,
        analysis: {
          positive_sentiment: 5,
          negative_sentiment: 5,
          neutral_sentiment: 1,
        },
      })
    );
    expect(result.metrics.sentiment).toBe("neutral");
  });
});

describe("transformTranscript - transcription string / array fallback", () => {
  it("parses a stringified transcription array", () => {
    const result = transformTranscript(
      asBackend({
        id: 5,
        transcription: '[{"speaker":"A","start_time":1,"text":"x"}]',
      })
    );
    expect(result.transcription).toHaveLength(1);
    const entry = (result.transcription as { speaker: string; end_time: number }[])[0];
    expect(entry.speaker).toBe("A");
    expect(entry.end_time).toBeCloseTo(1.01);
    // wordCount derived from text when word_count is absent.
    expect(result.metrics.wordCount).toBe(1);
  });

  it("derives duration from first/last start_time and word count from text", () => {
    const result = transformTranscript(
      asBackend({
        id: 7,
        transcription: [
          { speaker: "A", start_time: 2, text: "a b c" },
          { speaker: "B", start_time: 12, text: "d" },
        ],
      })
    );
    expect(result.duration).toBe(10);
    expect(result.metrics.wordCount).toBe(4);
    expect(result.transcription).toHaveLength(2);
  });
});
