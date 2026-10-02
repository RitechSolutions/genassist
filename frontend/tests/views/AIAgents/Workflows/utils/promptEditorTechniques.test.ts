import { describe, expect, it } from "vitest";
import {
  MAX_PHRASES,
  MAX_PHRASE_LENGTH,
  phrasesProblem,
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
