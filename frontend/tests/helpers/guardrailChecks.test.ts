import { describe, expect, it } from "vitest";
import {
  defaultGuardrailPolicy,
  extractGuardrailChecks,
  guardrailChipsByMessage,
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

describe("extractGuardrailChecks", () => {
  it("reads the checks from row_agent_response", () => {
    const checks = extractGuardrailChecks({
      row_agent_response: {
        guardrail_events: [verdict("prompt_attack", "blocked")],
      },
      guardrail_events: [verdict("blocked_words", "flagged")],
    });
    expect(checks.map((c) => [c.check_type, c.action])).toEqual([
      ["prompt_attack", "blocked"],
    ]);
  });

  it("falls back to the top-level checks", () => {
    const checks = extractGuardrailChecks({
      row_agent_response: { output: "Hi" },
      guardrail_events: [verdict("too_long", "skipped", "tool")],
    });
    expect(checks.map((c) => [c.check_type, c.action])).toEqual([
      ["too_long", "skipped"],
    ]);
  });

  it("drops entries without a check type and action", () => {
    const checks = extractGuardrailChecks({
      guardrail_events: [
        verdict("denied_topic", "flagged"),
        { ...verdict("prompt_attack", "blocked"), action: undefined },
        { ...verdict("prompt_attack", "blocked"), check_type: 3 },
        "blocked",
        null,
      ],
    });
    expect(checks.map((c) => c.check_type)).toEqual(["denied_topic"]);
  });
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
