import type {
  RuleConversation,
  RuleScopeTarget,
} from "@/interfaces/testEvaluation.interface";

// Turn targets are stored as lists; the single-turn fields are what earlier rules
// saved and are read as a one-item list.
export const targetedTurnIndexes = (rule: RuleScopeTarget): number[] => {
  const indexes = [...(rule.target_turn_indexes ?? [])];
  if (rule.target_turn_index != null) indexes.push(rule.target_turn_index);
  return [...new Set(indexes)].sort((a, b) => a - b);
};

// Plain-language "when" half of a rule summary, shared by every rule builder.
export const scopePhrase = (
  rule: RuleScopeTarget,
  conversations: RuleConversation[],
): string => {
  if (rule.scope === "conversation") return "during the conversation";
  if (rule.scope !== "specific_turn") return "on every turn";

  const conversation = conversations.find(
    (item) => item.id === rule.target_source_conversation_id,
  );
  const indexes = targetedTurnIndexes(rule);
  if (!conversation || indexes.length === 0) return "on the selected turns";

  const labels = indexes.map((index) => {
    const turn = conversation.turns.find((item) => item.turnIndex === index);
    return turn?.label ?? `Turn ${index + 1}`;
  });
  return `on ${conversation.label}, ${labels.join(", ")}`;
};

// A specific-turn rule with no turn picked cannot be graded, so saving is blocked.
export const scopeTargetIncomplete = (rule: RuleScopeTarget): boolean =>
  rule.scope === "specific_turn" &&
  (!rule.target_source_conversation_id || targetedTurnIndexes(rule).length === 0);
