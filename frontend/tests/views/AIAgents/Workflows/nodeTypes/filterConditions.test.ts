import { describe, it, expect } from "vitest";
import {
  describeFilterCondition,
  FILTER_OPERATOR_GROUPS,
  FILTER_OPERATORS,
  filterOperatorIsText,
  filterOperatorLabel,
  filterOperatorNeedsValue,
} from "@/views/AIAgents/Workflows/nodeTypes/router/filterConditions";

describe("FILTER_OPERATORS", () => {
  it("lists every engine operator once, in the backend's order", () => {
    // Mirrors backend engine/conditions.py OPERATORS.
    expect(FILTER_OPERATORS.map((o) => o.value)).toEqual([
      "equal",
      "not_equal",
      "contains",
      "not_contain",
      "starts_with",
      "not_starts_with",
      "ends_with",
      "not_ends_with",
      "regex",
      "greater_than",
      "greater_than_or_equal",
      "less_than",
      "less_than_or_equal",
      "is_empty",
      "is_not_empty",
    ]);
  });

  it("puts every operator in a displayed group", () => {
    const groups = new Set(FILTER_OPERATOR_GROUPS.map((g) => g.group));
    for (const o of FILTER_OPERATORS) expect(groups.has(o.group)).toBe(true);
  });
});

describe("operator helpers", () => {
  it("labels operators, defaulting to Equals", () => {
    expect(filterOperatorLabel("greater_than_or_equal")).toBe("Greater than or equal");
    expect(filterOperatorLabel(undefined)).toBe("Equals");
  });

  it("only asks for a value when the operator compares against one", () => {
    expect(filterOperatorNeedsValue("equal")).toBe(true);
    expect(filterOperatorNeedsValue("less_than")).toBe(true);
    expect(filterOperatorNeedsValue("is_empty")).toBe(false);
    expect(filterOperatorNeedsValue("is_not_empty")).toBe(false);
  });

  it("treats only text operators as case-sensitive-capable", () => {
    expect(filterOperatorIsText("contains")).toBe(true);
    expect(filterOperatorIsText("regex")).toBe(true);
    expect(filterOperatorIsText("greater_than")).toBe(false);
    expect(filterOperatorIsText("is_empty")).toBe(false);
  });
});

describe("describeFilterCondition", () => {
  it("summarises the condition for the node card", () => {
    expect(describeFilterCondition("equal", " active ")).toBe("Equals active");
    expect(describeFilterCondition("greater_than", "0.8")).toBe("Greater than 0.8");
    expect(describeFilterCondition("is_not_empty", "ignored")).toBe("Is not empty");
    expect(describeFilterCondition("contains", "")).toBe("Contains …");
    expect(describeFilterCondition(undefined, undefined)).toBe("Equals …");
  });
});
