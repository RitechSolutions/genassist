import { describe, expect, it } from "vitest";
import { toolExpectedText, toolRuleSummary } from "@/views/TestSuites/helpers/toolRuleText";

const summary = (overrides: Partial<Parameters<typeof toolRuleSummary>[0]> = {}) =>
  toolRuleSummary({
    agentId: null,
    toolLabels: [],
    operator: "all",
    scope: "on every turn",
    ...overrides,
  });

describe("toolRuleSummary", () => {
  it("reads an empty 'only' rule as no tools allowed", () => {
    expect(summary({ operator: "only" })).toBe("Any agent must not use any tools on every turn.");
  });

  it("lists the allowed tools of an 'only' rule", () => {
    expect(summary({ operator: "only", toolLabels: ["Search", "Lookup"] })).toBe(
      'Any agent may only use "Search" or "Lookup" on every turn.',
    );
  });

  it("forbids the named tools", () => {
    expect(summary({ operator: "none", toolLabels: ["Refund"] })).toBe(
      'Any agent must not use "Refund" on every turn.',
    );
  });

  it("requires every tool, or at least one, with optional success", () => {
    expect(
      summary({ operator: "all", toolLabels: ["A", "B", "C"], requireSuccess: true }),
    ).toBe('Any agent must successfully use "A", "B" and "C" on every turn.');
    expect(summary({ operator: "any", toolLabels: ["A", "B"] })).toBe(
      'Any agent must use "A" or "B" on every turn.',
    );
  });

  it("names the agent like the backend does", () => {
    expect(
      summary({ agentId: "agent-1", agentLabel: "Billing agent", toolLabels: ["Refund"] }),
    ).toBe('Billing agent must use "Refund" on every turn.');
    // An agent missing from the catalog is not "any agent".
    expect(summary({ agentId: "agent-1", toolLabels: ["Refund"] })).toBe(
      'The agent must use "Refund" on every turn.',
    );
  });

  it("ends with the scope phrase", () => {
    expect(summary({ toolLabels: ["A"], scope: "during the conversation" })).toBe(
      'Any agent must use "A" during the conversation.',
    );
  });
});

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
