import { describe, expect, it } from "vitest";
import { SOURCE_SUB_ROWS, isSourceSubRowParent, subRowCountLabel } from "@/views/Analytics/helpers/llmUsageSubRows";

describe("SOURCE_SUB_ROWS", () => {
  it("drills each expandable usage type into its own dimension", () => {
    expect(SOURCE_SUB_ROWS.evaluation.dimension).toBe("evaluation_method");
    expect(SOURCE_SUB_ROWS.llm_analyst.dimension).toBe("analyst_purpose");
  });
});

describe("isSourceSubRowParent", () => {
  it("accepts only the expandable usage types", () => {
    expect(isSourceSubRowParent("evaluation")).toBe(true);
    expect(isSourceSubRowParent("llm_analyst")).toBe(true);
    expect(isSourceSubRowParent("workflow")).toBe(false);
    expect(isSourceSubRowParent("toString")).toBe(false);
  });
});

describe("subRowCountLabel", () => {
  it("pluralises the parent's unit", () => {
    expect(subRowCountLabel("evaluation", 1)).toBe("1 method");
    expect(subRowCountLabel("evaluation", 2)).toBe("2 methods");
    expect(subRowCountLabel("llm_analyst", 1)).toBe("1 analysis");
    expect(subRowCountLabel("llm_analyst", 2)).toBe("2 analyses");
  });

  it("stays empty until there is a count", () => {
    expect(subRowCountLabel("llm_analyst", undefined)).toBeNull();
    expect(subRowCountLabel("llm_analyst", 0)).toBeNull();
  });
});
