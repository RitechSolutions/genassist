import { describe, expect, it } from "vitest";
import {
  HOSTILITY_POSITIVE_MAX,
  HOSTILITY_NEUTRAL_MAX,
  getSentimentFromHostility,
  getEffectiveSentiment,
  getSentimentStyles,
  formatDuration,
  formatCallTimestamp,
  formatDateTime,
  formatMetric,
  getTranscriptTypeLabel,
  formatMessageTime,
} from "@/views/Transcripts/helpers/formatting";
import type { Transcript } from "@/interfaces/transcript.interface";

const asTranscript = (value: unknown): Transcript => value as Transcript;

describe("hostility constants", () => {
  it("pins the documented thresholds", () => {
    expect(HOSTILITY_POSITIVE_MAX).toBe(20);
    expect(HOSTILITY_NEUTRAL_MAX).toBe(49);
  });
});

describe("getSentimentFromHostility", () => {
  it("returns positive at or below the positive max", () => {
    expect(getSentimentFromHostility(0)).toBe("positive");
    expect(getSentimentFromHostility(20)).toBe("positive");
  });

  it("returns neutral between the thresholds", () => {
    expect(getSentimentFromHostility(21)).toBe("neutral");
    expect(getSentimentFromHostility(49)).toBe("neutral");
  });

  it("returns negative above the neutral max", () => {
    expect(getSentimentFromHostility(50)).toBe("negative");
    expect(getSentimentFromHostility(100)).toBe("negative");
  });
});

describe("getEffectiveSentiment", () => {
  it("derives sentiment from the top-level hostility score when live", () => {
    expect(
      getEffectiveSentiment(
        asTranscript({ status: "in_progress", in_progress_hostility_score: 10 })
      )
    ).toBe("positive");
    expect(
      getEffectiveSentiment(
        asTranscript({ status: "takeover", in_progress_hostility_score: 60 })
      )
    ).toBe("negative");
  });

  it("falls back to metrics hostility score when live and top-level is absent", () => {
    expect(
      getEffectiveSentiment(
        asTranscript({
          status: "in_progress",
          metrics: { in_progress_hostility_score: 30 },
        })
      )
    ).toBe("neutral");
  });

  it("uses a hostility score of 0 when live and none is provided", () => {
    expect(
      getEffectiveSentiment(asTranscript({ status: "in_progress" }))
    ).toBe("positive");
  });

  it("uses the stored metrics sentiment for finalized conversations", () => {
    expect(
      getEffectiveSentiment(
        asTranscript({ status: "finalized", metrics: { sentiment: "negative" } })
      )
    ).toBe("negative");
  });

  it("defaults to neutral for finalized conversations without a sentiment", () => {
    expect(getEffectiveSentiment(asTranscript({ status: "finalized" }))).toBe(
      "neutral"
    );
    expect(
      getEffectiveSentiment(asTranscript({ status: "finalized", metrics: {} }))
    ).toBe("neutral");
  });

  it("throws for a null transcript (no optional chaining on the final read)", () => {
    expect(() => getEffectiveSentiment(asTranscript(null))).toThrow();
  });
});

describe("getSentimentStyles", () => {
  it("maps known sentiments to classes (case-insensitive)", () => {
    expect(getSentimentStyles("positive")).toBe("bg-green-100 text-green-800");
    expect(getSentimentStyles("POSITIVE")).toBe("bg-green-100 text-green-800");
    expect(getSentimentStyles("neutral")).toBe("bg-yellow-100 text-yellow-800");
    expect(getSentimentStyles("negative")).toBe("bg-red-100 text-red-800");
    expect(getSentimentStyles("very-bad")).toBe("bg-red-100 text-red-800");
  });

  it("returns the gray default for unknown, empty, or null values", () => {
    expect(getSentimentStyles("unknown")).toBe("bg-gray-100 text-gray-800");
    expect(getSentimentStyles("")).toBe("bg-gray-100 text-gray-800");
    expect(getSentimentStyles()).toBe("bg-gray-100 text-gray-800");
    expect(getSentimentStyles(null as unknown as string)).toBe(
      "bg-gray-100 text-gray-800"
    );
  });
});

describe("formatDuration", () => {
  it("formats minutes and seconds", () => {
    expect(formatDuration(0)).toBe("0:00");
    expect(formatDuration(65)).toBe("1:05");
    expect(formatDuration(59.9)).toBe("0:59");
  });

  it("formats hours when present", () => {
    expect(formatDuration(3661)).toBe("1:01:01");
  });

  it("clamps negatives to zero and defaults to 0 seconds", () => {
    expect(formatDuration(-5)).toBe("0:00");
    expect(formatDuration()).toBe("0:00");
  });
});

describe("formatCallTimestamp", () => {
  it("formats non-padded minutes and padded seconds", () => {
    expect(formatCallTimestamp(0)).toBe("0:00");
    expect(formatCallTimestamp(9)).toBe("0:09");
    expect(formatCallTimestamp(65)).toBe("1:05");
    expect(formatCallTimestamp(125)).toBe("2:05");
    expect(formatCallTimestamp(600)).toBe("10:00");
  });

  it("returns 00:00 for negative or NaN input", () => {
    expect(formatCallTimestamp(-1)).toBe("00:00");
    expect(formatCallTimestamp(NaN)).toBe("00:00");
  });

  it("defaults to 0:00", () => {
    expect(formatCallTimestamp()).toBe("0:00");
  });
});

describe("formatDateTime", () => {
  it("returns N/A for empty or default input", () => {
    expect(formatDateTime("")).toBe("N/A");
    expect(formatDateTime()).toBe("N/A");
  });

  it("returns Invalid Date for an unparseable string", () => {
    expect(formatDateTime("not a date")).toBe("Invalid Date");
  });

  it("returns a formatted, non-sentinel string for a valid date", () => {
    const result = formatDateTime("2020-01-01T00:00:00Z");
    expect(typeof result).toBe("string");
    expect(result.length).toBeGreaterThan(0);
    expect(result).not.toBe("N/A");
    expect(result).not.toBe("Invalid Date");
  });
});

describe("formatMetric", () => {
  it("formats with the default precision of 1", () => {
    expect(formatMetric(1.234567)).toBe("1.2");
    expect(formatMetric(5)).toBe("5.0");
    expect(formatMetric(0)).toBe("0.0");
    expect(formatMetric()).toBe("0.0");
  });

  it("honors a custom precision", () => {
    expect(formatMetric(1.234567, 3)).toBe("1.235");
    expect(formatMetric(3.7, 0)).toBe("4");
  });

  it("returns 0.0 for NaN or non-numeric input", () => {
    expect(formatMetric(NaN)).toBe("0.0");
    expect(formatMetric("abc" as unknown as number)).toBe("0.0");
  });
});

describe("getTranscriptTypeLabel", () => {
  it("returns Unknown when transcript or metadata is missing", () => {
    expect(getTranscriptTypeLabel(asTranscript(null))).toBe("Unknown");
    expect(getTranscriptTypeLabel(asTranscript({}))).toBe("Unknown");
  });

  it("returns Call when a customer_speaker is set", () => {
    expect(
      getTranscriptTypeLabel(
        asTranscript({ metadata: { customer_speaker: "Customer" } })
      )
    ).toBe("Call");
  });

  it("returns Chat when there is no customer_speaker", () => {
    expect(
      getTranscriptTypeLabel(asTranscript({ metadata: {} }))
    ).toBe("Chat");
    expect(
      getTranscriptTypeLabel(
        asTranscript({ metadata: { customer_speaker: "" } })
      )
    ).toBe("Chat");
  });
});

describe("formatMessageTime", () => {
  const TIME_RE = /^\d{2}:\d{2}:\d{2}$/;

  it("returns an empty string for falsy input", () => {
    expect(formatMessageTime(undefined)).toBe("");
    expect(formatMessageTime("")).toBe("");
    expect(formatMessageTime(0)).toBe("");
  });

  it("formats a numeric epoch-seconds value as HH:MM:SS", () => {
    expect(formatMessageTime(1600000000)).toMatch(TIME_RE);
  });

  it("formats an ISO string (contains 'T') as HH:MM:SS", () => {
    expect(formatMessageTime("2020-01-01T12:34:56Z")).toMatch(TIME_RE);
  });

  it("formats a space-separated datetime string as HH:MM:SS", () => {
    expect(formatMessageTime("2020-01-01 12:34:56")).toMatch(TIME_RE);
  });

  it("parses a numeric string with no T/space as epoch seconds", () => {
    expect(formatMessageTime("1600000000")).toMatch(TIME_RE);
  });

  it("returns an empty string for a non-numeric string with no T/space", () => {
    expect(formatMessageTime("abc")).toBe("");
  });

  it("returns an empty string for an invalid date that contains 'T'", () => {
    expect(formatMessageTime("notadateT")).toBe("");
  });
});
