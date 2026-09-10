import { describe, expect, it } from "vitest";
import { promptEditorCapabilities } from "@/views/AIAgents/Workflows/utils/promptEditorCapabilities";

describe("promptEditorCapabilities", () => {
  it("grants everything to the admin wildcard", () => {
    expect(promptEditorCapabilities(["*"])).toEqual({
      canEditPrompt: true,
      canOptimize: true,
      canEvaluate: true,
      canReadCases: true,
      canEditCases: true,
    });
  });

  it("maps update:evaluation to authoring only", () => {
    const caps = promptEditorCapabilities(["update:evaluation"]);

    expect(caps.canEditPrompt).toBe(true);
    expect(caps.canOptimize).toBe(true);
    expect(caps.canEvaluate).toBe(false);
    expect(caps.canReadCases).toBe(false);
  });

  it("maps run:evaluation to evaluating only", () => {
    const caps = promptEditorCapabilities(["run:evaluation"]);

    expect(caps.canEvaluate).toBe(true);
    expect(caps.canEditPrompt).toBe(false);
    expect(caps.canOptimize).toBe(false);
  });

  it("separates reading cases from editing them", () => {
    const caps = promptEditorCapabilities(["read:workflow"]);

    expect(caps.canReadCases).toBe(true);
    expect(caps.canEditCases).toBe(false);
  });

  it("grants nothing without permissions", () => {
    expect(Object.values(promptEditorCapabilities([]))).toEqual([
      false,
      false,
      false,
      false,
      false,
    ]);
  });
});
