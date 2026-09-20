import { promptLength } from "./promptEditorGates";

export { splitForbiddenPhrases } from "@/views/TestSuites/helpers/evaluationForm";

export const MAX_CHECK_CASES = 25;
export const CASES_TO_CHECK_OPTIONS = [5, 10, 25] as const;
export const DEFAULT_CASES_TO_CHECK = 10;

/** Techniques an isolated check can grade. `field_equals` stays API-only and
 *  `provenance_eval` is rejected server-side, so neither is offered */
export const PROMPT_CHECK_TECHNIQUES = [
  "exact_match",
  "contains",
  "json_match",
  "not_contains",
  "nli_eval",
  "llm_judge",
] as const;

export const MAX_PHRASES = 50;
export const MAX_PHRASE_LENGTH = 200;
export const MAX_RUBRIC_LENGTH = 2_000;

/** Grades the reply on its own, so it scores every case on the first run */
export const DEFAULT_JUDGE_RUBRIC =
  "Score from 0.0 to 1.0 how well the reply answers the question correctly, " +
  "completely and in the intended tone.";

/** The score text as a number. Null for a blank box, which leaves the server default */
export const parseEntailScore = (text: string): number | null =>
  text.trim() === "" ? null : Number(text);

/** Null when the value is sendable. Mirrors the bound the endpoint enforces */
const unitScoreProblem = (score: number | null, noun: string): string | null => {
  if (score === null) return null;
  return Number.isFinite(score) && score >= 0 && score <= 1
    ? null
    : `Use a minimum ${noun} score between 0 and 1.`;
};

export const entailScoreProblem = (score: number | null): string | null =>
  unitScoreProblem(score, "entailment");

export const judgeScoreProblem = (score: number | null): string | null =>
  unitScoreProblem(score, "judge");

export const rubricProblem = (rubric: string): string | null => {
  const text = rubric.trim();
  if (!text) return "Write a rubric for the judge.";
  return promptLength(text) > MAX_RUBRIC_LENGTH
    ? `The rubric must be ${MAX_RUBRIC_LENGTH.toLocaleString()} characters or fewer.`
    : null;
};

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
