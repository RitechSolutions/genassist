import { describe, expect, it } from "vitest";
import { METHOD_LABELS, methodLabel } from "@/views/TestSuites/helpers/methodLabels";

describe("METHOD_LABELS", () => {
  it("maps every known technique key to its friendly label", () => {
    expect(METHOD_LABELS).toEqual({
      exact_match: "Exact Match",
      contains: "Contains",
      not_contains: "Does Not Contain",
      json_match: "JSON Match",
      field_equals: "Field Equals",
      tool_used: "Tool Usage",
      route_taken: "Route Taken",
      action_taken: "Action Taken",
      no_errors: "No Errors",
      nli_eval: "NLI Evaluation",
      provenance_eval: "Provenance Evaluation",
      llm_judge: "LLM Judge",
    });
  });
});

describe("methodLabel", () => {
  it("returns the friendly label for a known technique", () => {
    expect(methodLabel("exact_match")).toBe("Exact Match");
    expect(methodLabel("tool_used")).toBe("Tool Usage");
    expect(methodLabel("llm_judge")).toBe("LLM Judge");
  });

  it("falls back to the raw technique key when unknown", () => {
    expect(methodLabel("unknown_technique")).toBe("unknown_technique");
  });

  it("returns the empty string unchanged (not in the map)", () => {
    expect(methodLabel("")).toBe("");
  });

  it("is case sensitive and does not match differently-cased keys", () => {
    expect(methodLabel("Exact_Match")).toBe("Exact_Match");
    expect(methodLabel("EXACT_MATCH")).toBe("EXACT_MATCH");
  });
});
