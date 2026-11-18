import { describe, expect, it } from "vitest";
import {
  defaultGuardrailPolicy,
  guardrailChipsByMessage,
  guardrailLimitError,
  usesJudge,
} from "@/helpers/guardrailChecks";

const checks = () => {
  const { prompt_attack, harmful_content, denied_topics, blocked_words } =
    defaultGuardrailPolicy();
  return { prompt_attack, harmful_content, denied_topics, blocked_words };
};

describe("usesJudge", () => {
  it("needs no judge when only blocked words are on", () => {
    expect(usesJudge({ ...checks(), blocked_words: ["competitorX"] })).toBe(
      false
    );
  });

  it("needs a judge for prompt attacks", () => {
    expect(usesJudge({ ...checks(), prompt_attack: "low" })).toBe(true);
  });

  it("needs a judge for one harm category", () => {
    const value = checks();
    expect(
      usesJudge({
        ...value,
        harmful_content: { ...value.harmful_content, self_harm: "high" },
      })
    ).toBe(true);
  });

  it("needs a judge for denied topics alone", () => {
    expect(
      usesJudge({
        ...checks(),
        denied_topics: [
          { name: "Legal advice", definition: "Court advice", examples: [] },
        ],
      })
    ).toBe(true);
  });

  it("needs a judge when tool results are checked", () => {
    expect(usesJudge(checks(), "flag")).toBe(true);
    expect(usesJudge(checks(), "off")).toBe(false);
  });
});

describe("guardrailLimitError", () => {
  const topic = (example: string) => ({
    name: "Legal advice",
    definition: "Court advice",
    examples: [example],
  });

  it("allows values right at the limits", () => {
    expect(
      guardrailLimitError({
        blocked_words: Array.from({ length: 200 }, (_, i) =>
          `w${i}`.padEnd(100, "x")
        ),
        denied_topics: [topic("e".repeat(200))],
      })
    ).toBeNull();
  });

  it("flags more than 200 blocked words", () => {
    expect(
      guardrailLimitError({
        blocked_words: Array.from({ length: 201 }, (_, i) => `w${i}`),
        denied_topics: [],
      })
    ).toBe("Keep blocked words to 200 or fewer.");
  });

  it("flags a blocked word over 100 characters", () => {
    expect(
      guardrailLimitError({
        blocked_words: ["ok", "w".repeat(101)],
        denied_topics: [],
      })
    ).toBe("Keep each blocked word to 100 characters or fewer.");
  });

  it("flags a topic example over 200 characters", () => {
    expect(
      guardrailLimitError({
        blocked_words: [],
        denied_topics: [topic("short"), topic("e".repeat(201))],
      })
    ).toBe("Keep each topic example to 200 characters or fewer.");
  });
});

const verdict = (check_type: string, action: string, stage = "input") => ({
  stage,
  check_type,
  category: null,
  detector: "judge",
  score: 2,
  mode: "block",
  action,
  source: null,
});

describe("guardrailChipsByMessage", () => {
  const event = (
    transcript_message_id: string | null,
    action: "blocked" | "flagged" | "error" | "passed" | "skipped"
  ) => ({
    ...verdict("prompt_attack", action),
    stage: "input" as const,
    action,
    id: `ev-${transcript_message_id}-${action}`,
    transcript_message_id,
    created_at: "2026-11-18T10:00:00Z",
  });

  it("marks a message blocked over flagged, whatever the order", () => {
    expect(
      guardrailChipsByMessage([
        event("m1", "flagged"),
        event("m1", "blocked"),
        event("m2", "blocked"),
        event("m2", "flagged"),
        event("m3", "flagged"),
      ])
    ).toEqual({ m1: "blocked", m2: "blocked", m3: "flagged" });
  });

  it("ignores errors, skipped checks and events with no message", () => {
    expect(
      guardrailChipsByMessage([
        event("m1", "error"),
        event("m2", "skipped"),
        event("m3", "passed"),
        event(null, "blocked"),
        event("m4", "flagged"),
      ])
    ).toEqual({ m4: "flagged" });
  });
});
