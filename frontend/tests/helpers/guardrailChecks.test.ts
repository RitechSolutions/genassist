import { describe, expect, it } from "vitest";
import { defaultGuardrailPolicy, usesJudge } from "@/helpers/guardrailChecks";

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
