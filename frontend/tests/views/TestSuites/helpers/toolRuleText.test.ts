import { describe, expect, it } from "vitest";
import { toolExpectedText } from "@/views/TestSuites/helpers/toolRuleText";

describe("toolExpectedText", () => {
  it("reads an empty 'only' rule as no tools allowed", () => {
    expect(toolExpectedText({ rule: { operator: "only", tool_ids: [] } })).toBe(
      "Do not use any tools.",
    );
  });

  it("names the allowed tools of an 'only' rule", () => {
    expect(
      toolExpectedText({
        rule: { operator: "only", tool_ids: ["t1"] },
        tools: { t1: { label: "Search" } },
      }),
    ).toBe('Use only "Search".');
  });
});
