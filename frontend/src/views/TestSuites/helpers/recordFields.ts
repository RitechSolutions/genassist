/** Reading and writing a dataset record as plain text.
 *
 * A record is two JSON objects, but the engine only treats a narrow shape as
 * text, so the UI may only offer text editing for exactly that shape:
 *
 *  - input_data must carry a string `message`. The chat input node declares it
 *    required, so a record without one fails to execute rather than scoring low.
 *  - expected_output is unwrapped by the backend's normalize_text only when it
 *    has exactly ONE key, that key is "value" or "text", and its value is a
 *    string. Every other shape is scored against its Python repr, braces and
 *    all — so a second key silently changes what the record means.
 *
 * Anything outside that shape stays JSON in the UI. These predicates mirror
 * backend/app/services/evaluation_text.py:17-29.
 */

/** Keys normalize_text unwraps, in its own precedence order. */
const TEXT_KEYS = ["value", "text"] as const;

/** The key we write, matching what conversation import produces. */
export const ANSWER_KEY = "value";

/** The key the chat input node requires. */
export const QUESTION_KEY = "message";

const onlyKey = (obj: Record<string, unknown>): string | null => {
  const keys = Object.keys(obj);
  return keys.length === 1 ? keys[0] : null;
};

/** The record's question, or null when its input is not plain text. */
export const questionOf = (
  input?: Record<string, unknown> | null,
): string | null => {
  if (!input) return null;
  if (onlyKey(input) !== QUESTION_KEY) return null;
  const value = input[QUESTION_KEY];
  return typeof value === "string" ? value : null;
};

/** The record's expected answer, or null when the scorer would not unwrap it. */
export const answerOf = (
  expected?: Record<string, unknown> | null,
): string | null => {
  if (!expected) return null;
  const key = onlyKey(expected);
  if (!key || !TEXT_KEYS.includes(key as (typeof TEXT_KEYS)[number])) return null;
  const value = expected[key];
  return typeof value === "string" ? value : null;
};

/** True when both halves round-trip through text without losing anything. */
export const isPlainRecord = (
  input?: Record<string, unknown> | null,
  expected?: Record<string, unknown> | null,
): boolean =>
  questionOf(input) !== null && (!hasExpected(expected) || answerOf(expected) !== null);

/** An expected_output that carries something — {} counts as absent. */
export const hasExpected = (
  expected?: Record<string, unknown> | null,
): boolean => !!expected && Object.keys(expected).length > 0;

export const questionToInput = (text: string): Record<string, unknown> => ({
  [QUESTION_KEY]: text,
});

/** Undefined for blank text, so the record is saved without an expected output. */
export const answerToExpected = (
  text: string,
): Record<string, unknown> | undefined =>
  text.trim() ? { [ANSWER_KEY]: text } : undefined;

export interface ParsedObject {
  ok: boolean;
  value?: Record<string, unknown>;
  error?: string;
}

/** Parses a JSON object, rejecting the scalars and arrays the API would 422 on. */
export const parseRecordObject = (raw: string): ParsedObject => {
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    return { ok: false, error: "Not valid JSON." };
  }
  if (parsed === null || typeof parsed !== "object" || Array.isArray(parsed)) {
    return { ok: false, error: "Must be a JSON object, e.g. {\"message\": \"...\"}." };
  }
  return { ok: true, value: parsed as Record<string, unknown> };
};
