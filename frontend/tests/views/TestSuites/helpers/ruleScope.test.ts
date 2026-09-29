import { describe, expect, it } from "vitest";
import { scopePhrase, scopeTargetIncomplete } from "@/views/TestSuites/helpers/ruleScope";
import type {
  RuleConversation,
  RuleScopeTarget,
} from "@/interfaces/testEvaluation.interface";

const conversations: RuleConversation[] = [
  {
    id: "conv-1",
    label: "Conversation 1",
    turns: [
      { caseId: "case-1", turnIndex: 0, label: "Turn 1" },
      { caseId: "case-2", turnIndex: 1, label: "Turn 2" },
    ],
  },
];

const rule = (overrides: Partial<RuleScopeTarget> = {}): RuleScopeTarget => ({
  scope: "every_turn",
  ...overrides,
});

describe("scopePhrase", () => {
  it("describes every-turn and conversation scopes", () => {
    expect(scopePhrase(rule(), conversations)).toBe("on every turn");
    expect(scopePhrase(rule({ scope: "conversation" }), conversations)).toBe(
      "during the conversation",
    );
  });

  it("names the targeted conversation and turn", () => {
    const targeted = rule({
      scope: "specific_turn",
      target_source_conversation_id: "conv-1",
      target_turn_indexes: [1],
    });
    expect(scopePhrase(targeted, conversations)).toBe("on Conversation 1, Turn 2");
  });

  it("names every targeted turn, in order", () => {
    const targeted = rule({
      scope: "specific_turn",
      target_source_conversation_id: "conv-1",
      target_turn_indexes: [1, 0],
    });
    expect(scopePhrase(targeted, conversations)).toBe("on Conversation 1, Turn 1, Turn 2");
  });

  it("reads a rule saved with the older single-turn field", () => {
    const targeted = rule({
      scope: "specific_turn",
      target_source_conversation_id: "conv-1",
      target_turn_index: 0,
    });
    expect(scopePhrase(targeted, conversations)).toBe("on Conversation 1, Turn 1");
  });

  it("stays generic while no turn is picked", () => {
    const targeted = rule({ scope: "specific_turn", target_source_conversation_id: "conv-1" });
    expect(scopePhrase(targeted, conversations)).toBe("on the selected turns");
  });

  it("stays generic when the targeted conversation is not in this dataset", () => {
    const targeted = rule({
      scope: "specific_turn",
      target_source_conversation_id: "gone",
      target_turn_indexes: [0],
    });
    expect(scopePhrase(targeted, conversations)).toBe("on the selected turns");
  });
});

describe("scopeTargetIncomplete", () => {
  it("blocks saving a specific-turn rule with no turn picked", () => {
    expect(scopeTargetIncomplete(rule({ scope: "specific_turn" }))).toBe(true);
    expect(
      scopeTargetIncomplete(
        rule({ scope: "specific_turn", target_source_conversation_id: "conv-1" }),
      ),
    ).toBe(true);
    expect(
      scopeTargetIncomplete(
        rule({
          scope: "specific_turn",
          target_source_conversation_id: "conv-1",
          target_turn_indexes: [],
        }),
      ),
    ).toBe(true);
  });

  it("allows one or more picked turns, and every other scope", () => {
    expect(
      scopeTargetIncomplete(
        rule({
          scope: "specific_turn",
          target_source_conversation_id: "conv-1",
          target_turn_indexes: [0, 1],
        }),
      ),
    ).toBe(false);
    expect(scopeTargetIncomplete(rule({ scope: "conversation" }))).toBe(false);
    expect(scopeTargetIncomplete(rule())).toBe(false);
  });
});
