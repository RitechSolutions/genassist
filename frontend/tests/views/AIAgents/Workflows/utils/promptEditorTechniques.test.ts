import { describe, expect, it } from "vitest";
import {
  MAX_PHRASES,
  MAX_PHRASE_LENGTH,
  MAX_RUBRIC_LENGTH,
  PROMPT_CHECK_TECHNIQUES,
  entailScoreProblem,
  judgeScoreProblem,
  phrasesProblem,
  rubricProblem,
} from "@/views/AIAgents/Workflows/utils/promptEditorTechniques";

describe("phrasesProblem", () => {
  it("accepts a list the endpoint takes", () => {
    expect(phrasesProblem(["refund", "guarantee"])).toBeNull();
  });

  it("blocks an empty list, which the evaluator would score as a silent failure", () => {
    expect(phrasesProblem([])).toBe("Add at least one forbidden phrase.");
  });

  it("blocks more phrases than the endpoint accepts", () => {
    expect(phrasesProblem(Array(MAX_PHRASES + 1).fill("x"))).toBe(
      "Use at most 50 forbidden phrases.",
    );
    expect(phrasesProblem(Array(MAX_PHRASES).fill("x"))).toBeNull();
  });

  it("blocks a phrase longer than the endpoint accepts", () => {
    expect(phrasesProblem(["ok", "x".repeat(MAX_PHRASE_LENGTH + 1)])).toBe(
      "Each forbidden phrase must be 200 characters or fewer.",
    );
    expect(phrasesProblem(["x".repeat(MAX_PHRASE_LENGTH)])).toBeNull();
  });
});

describe("rubricProblem", () => {
  it("blocks a rubric the judge could not grade with", () => {
    expect(rubricProblem("")).toBe("Write a rubric for the judge.");
    expect(rubricProblem("   ")).toBe("Write a rubric for the judge.");
  });

  it("holds the rubric to the bound the endpoint enforces, after stripping", () => {
    expect(rubricProblem("x".repeat(MAX_RUBRIC_LENGTH))).toBeNull();
    expect(rubricProblem(`  ${"x".repeat(MAX_RUBRIC_LENGTH)}  `)).toBeNull();
    expect(rubricProblem("x".repeat(MAX_RUBRIC_LENGTH + 1))).toBe(
      "The rubric must be 2,000 characters or fewer.",
    );
  });

  it("counts code points, as the endpoint does", () => {
    expect(rubricProblem("🙂".repeat(MAX_RUBRIC_LENGTH))).toBeNull();
    expect(rubricProblem("🙂".repeat(MAX_RUBRIC_LENGTH + 1))).not.toBeNull();
  });
});

describe("unit score problems", () => {
  it("shares one bound and differs only in what it names", () => {
    expect(entailScoreProblem(null)).toBeNull();
    expect(judgeScoreProblem(null)).toBeNull();
    expect(entailScoreProblem(0)).toBeNull();
    expect(judgeScoreProblem(1)).toBeNull();
    expect(entailScoreProblem(1.1)).toBe(
      "Use a minimum entailment score between 0 and 1.",
    );
    expect(judgeScoreProblem(-0.1)).toBe(
      "Use a minimum judge score between 0 and 1.",
    );
    expect(judgeScoreProblem(Number.NaN)).toBe(
      "Use a minimum judge score between 0 and 1.",
    );
  });
});

describe("PROMPT_CHECK_TECHNIQUES", () => {
  it("offers the judge and withholds the deferred and literal checks", () => {
    expect(PROMPT_CHECK_TECHNIQUES).toContain("llm_judge");
    expect(PROMPT_CHECK_TECHNIQUES).not.toContain("provenance_eval");
    expect(PROMPT_CHECK_TECHNIQUES).not.toContain("exact_match");
    expect(PROMPT_CHECK_TECHNIQUES).not.toContain("contains");
  });
});
