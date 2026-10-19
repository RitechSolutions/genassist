import { describe, expect, it } from "vitest";
import type {
  PromptOptimizeResponse,
  SuggestionOutcome,
} from "@/interfaces/promptEditor.interface";
import {
  effectiveOutcomeOf,
  gateOutcomeOf,
  suggestionOutcomeOf,
} from "@/views/AIAgents/Workflows/utils/promptEditorOutcome";

const result = (
  suggested_prompt: string,
  outcome: SuggestionOutcome,
): PromptOptimizeResponse =>
  ({ suggested_prompt, outcome }) as PromptOptimizeResponse;

describe("suggestionOutcomeOf", () => {
  it("is unchanged only for byte-identical text", () => {
    expect(suggestionOutcomeOf("a\nb", "a\nb")).toBe("unchanged");
    expect(suggestionOutcomeOf("a\nb", "a\nb\n")).not.toBe("unchanged");
  });

  it.each([
    ["CRLF line endings", "a\nb", "a\r\nb"],
    ["a trailing newline", "a\nb", "a\nb\n"],
    ["trailing spaces on a line", "a\nb", "a  \nb"],
    ["extra blank lines", "a\nb", "a\n\n\nb"],
    ["indentation", "a\nb", "a\n  b"],
  ])("treats %s as spacing only", (_label, base, text) => {
    expect(suggestionOutcomeOf(base, text)).toBe("whitespace_only");
  });

  it("is changed for a word change or an emptied text", () => {
    expect(suggestionOutcomeOf("a b", "a c")).toBe("changed");
    expect(suggestionOutcomeOf("a", "")).toBe("changed");
  });
});

describe("effectiveOutcomeOf", () => {
  it("trusts the server while the suggestion is the model's", () => {
    expect(effectiveOutcomeOf(result("a  b", "changed"), "a b", "a  b")).toBe(
      "changed",
    );
  });

  it("recomputes against the base once edited, so an edit back to the base counts as a no-op", () => {
    const changed = result("after", "changed");

    expect(effectiveOutcomeOf(changed, "before", "before")).toBe("unchanged");
    expect(effectiveOutcomeOf(changed, "before", "before\n")).toBe(
      "whitespace_only",
    );
    expect(effectiveOutcomeOf(null, "before", "before")).toBeNull();
  });
});

describe("gateOutcomeOf", () => {
  it("keeps a no-op on the prompt the chain started from gated", () => {
    expect(gateOutcomeOf("unchanged", "draft", "draft")).toBe("unchanged");
    expect(gateOutcomeOf("whitespace_only", "draft", "draft")).toBe(
      "whitespace_only",
    );
    expect(gateOutcomeOf("unchanged", "s1", null)).toBe("unchanged");
  });

  it("opens a no-op on an earlier suggestion, which the draft never got", () => {
    expect(gateOutcomeOf("unchanged", "s1", "draft")).toBeNull();
    expect(gateOutcomeOf("whitespace_only", "s1", "draft")).toBeNull();
  });
});
