export { splitForbiddenPhrases } from "@/views/TestSuites/helpers/evaluationForm";

export const MAX_CHECK_CASES = 25;
export const CASES_TO_CHECK_OPTIONS = [5, 10, 25] as const;
export const DEFAULT_CASES_TO_CHECK = 10;

/** Techniques an isolated check can grade. `field_equals` stays API-only, and
 *  `llm_judge` / `provenance_eval` are rejected server-side, so neither is offered */
export const PROMPT_CHECK_TECHNIQUES = [
  "exact_match",
  "contains",
  "json_match",
  "not_contains",
  "nli_eval",
] as const;

export const MAX_PHRASES = 50;
export const MAX_PHRASE_LENGTH = 200;

/** Null when the list is sendable. An empty list must never reach the server:
 *  the evaluator scores a silent red rather than skipping the check */
export const phrasesProblem = (phrases: readonly string[]): string | null => {
  if (phrases.length === 0) return "Add at least one forbidden phrase.";
  if (phrases.length > MAX_PHRASES)
    return `Use at most ${MAX_PHRASES} forbidden phrases.`;
  if (phrases.some((phrase) => phrase.length > MAX_PHRASE_LENGTH))
    return `Each forbidden phrase must be ${MAX_PHRASE_LENGTH} characters or fewer.`;
  return null;
};
