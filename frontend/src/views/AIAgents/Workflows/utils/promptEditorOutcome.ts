import type {
  PromptOptimizeResponse,
  SuggestionOutcome,
} from "@/interfaces/promptEditor.interface";

const normalize = (text: string): string => text.trim().split(/\s+/).join(" ");

export const suggestionOutcomeOf = (
  base: string,
  text: string,
): SuggestionOutcome =>
  text === base
    ? "unchanged"
    : normalize(text) === normalize(base)
      ? "whitespace_only"
      : "changed";

export const effectiveOutcomeOf = (
  result: PromptOptimizeResponse | null,
  optimizedFrom: string,
  suggestion: string,
): SuggestionOutcome | null =>
  result === null
    ? null
    : suggestion === result.suggested_prompt
      ? result.outcome
      : suggestionOutcomeOf(optimizedFrom, suggestion);

export const gateOutcomeOf = (
  outcome: SuggestionOutcome | null,
  optimizedFrom: string,
  chainOrigin: string | null,
): SuggestionOutcome | null =>
  chainOrigin !== null && optimizedFrom !== chainOrigin ? null : outcome;
