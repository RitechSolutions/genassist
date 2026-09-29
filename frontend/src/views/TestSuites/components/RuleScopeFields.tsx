import React from "react";
import { Label } from "@/components/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/select";
import { Check } from "lucide-react";
import { cn } from "@/helpers/utils";
import type {
  RuleConversation,
  RuleScope,
  RuleScopeTarget,
} from "@/interfaces/testEvaluation.interface";
import { targetedTurnIndexes } from "../helpers/ruleScope";
const SCOPE_OPTIONS: { value: RuleScope; label: string }[] = [
  { value: "every_turn", label: "Every turn" },
  { value: "conversation", label: "Whole conversation" },
  { value: "specific_turn", label: "Specific turn" },
];

const SCOPE_HINTS: Record<RuleScope, string> = {
  every_turn: "Checked on each turn separately",
  conversation: "Passes when it happens at least once in the conversation",
  specific_turn: "Checked on each turn you pick, in one conversation",
};

interface Props {
  rule: RuleScopeTarget;
  conversations: RuleConversation[];
  onChange: (patch: Partial<RuleScopeTarget>) => void;
  // Rendered beside the scope select (e.g. Tool Usage's "Must succeed" switch).
  children?: React.ReactNode;
}

export const RuleScopeFields: React.FC<Props> = ({
  rule,
  conversations,
  onChange,
  children,
}) => {
  const selectedConversation = conversations.find(
    (conversation) => conversation.id === rule.target_source_conversation_id,
  );

  const selectedTurns = targetedTurnIndexes(rule);

  // Written together so the pair stays consistent: ids point at this run's cases,
  // indexes survive a re-import of the same conversation.
  const setTurns = (turnIndexes: number[]) => {
    const turns = (selectedConversation?.turns ?? []).filter((turn) =>
      turnIndexes.includes(turn.turnIndex),
    );
    onChange({
      target_turn_indexes: turns.map((turn) => turn.turnIndex),
      target_case_ids: turns.map((turn) => turn.caseId),
      target_turn_index: null,
      target_case_id: null,
    });
  };

  const clearTargets = () => ({
    target_source_conversation_id: null,
    target_turn_indexes: [],
    target_case_ids: [],
    target_turn_index: null,
    target_case_id: null,
  });

  const changeScope = (scope: RuleScope) => {
    if (scope === "specific_turn") {
      onChange({ scope });
      return;
    }
    // Targets only mean something for specific turns; clear them otherwise.
    onChange({ scope, ...clearTargets() });
  };

  const selectConversation = (conversationId: string) =>
    onChange({
      ...clearTargets(),
      target_source_conversation_id: conversationId,
    });

  const toggleTurn = (turnIndex: number) =>
    setTurns(
      selectedTurns.includes(turnIndex)
        ? selectedTurns.filter((index) => index !== turnIndex)
        : [...selectedTurns, turnIndex],
    );

  return (
    <>
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label>When</Label>
          <Select value={rule.scope} onValueChange={(value) => changeScope(value as RuleScope)}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {SCOPE_OPTIONS.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <p className="text-xs text-muted-foreground">{SCOPE_HINTS[rule.scope]}</p>
        </div>
        {children}
      </div>

      {rule.scope === "specific_turn" &&
        (conversations.length === 0 ? (
          <p className="text-xs text-muted-foreground">
            No imported conversations in this dataset to target.
          </p>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label>Conversation</Label>
              <Select
                value={rule.target_source_conversation_id ?? ""}
                onValueChange={selectConversation}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select a conversation" />
                </SelectTrigger>
                <SelectContent>
                  {conversations.map((conversation) => (
                    <SelectItem key={conversation.id} value={conversation.id}>
                      {conversation.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label>Turns</Label>
              {!selectedConversation ? (
                <p className="text-xs text-muted-foreground">
                  Pick a conversation first.
                </p>
              ) : (
                <div className="flex flex-wrap gap-1.5">
                  {selectedConversation.turns.map((turn) => {
                    const selected = selectedTurns.includes(turn.turnIndex);
                    return (
                      <button
                        key={turn.caseId}
                        type="button"
                        aria-pressed={selected}
                        onClick={() => toggleTurn(turn.turnIndex)}
                        className={cn(
                          "inline-flex items-center gap-1 rounded-md border px-2 py-1 text-xs",
                          selected
                            ? "border-primary bg-primary/10 text-primary"
                            : "border-input text-muted-foreground hover:text-foreground",
                        )}
                      >
                        {selected && <Check className="h-3 w-3" />}
                        {turn.label}
                      </button>
                    );
                  })}
                </div>
              )}
              {selectedConversation && selectedTurns.length === 0 && (
                <p className="text-xs text-destructive">Pick at least one turn.</p>
              )}
              {selectedTurns.length > 1 && (
                <p className="text-xs text-muted-foreground">
                  Checked on each turn separately — one result per turn.
                </p>
              )}
            </div>
          </div>
        ))}
    </>
  );
};
