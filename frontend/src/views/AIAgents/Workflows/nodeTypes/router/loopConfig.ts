import type { LoopCollect, LoopMode, LoopOnError } from "../../types/nodes";

/** Mirrors engine/nodes/loop_node.py. */
export const DEFAULT_LOOP_MODE: LoopMode = "forEach";

export const LOOP_MODE_LABELS: Record<LoopMode, string> = {
  forEach: "For each item",
  repeatUntil: "Repeat until",
};

export const LOOP_ON_ERROR_LABELS: Record<LoopOnError, string> = {
  stop: "Stop the loop",
  continue: "Continue with the next pass",
};

export const LOOP_COLLECT_LABELS: Record<LoopCollect, string> = {
  all: "Every pass",
  last: "Only the last pass",
  none: "None",
};

/** Longest wait between two passes the server allows, also the ceiling of the doubling. */
export const LOOP_MAX_DELAY_SECONDS = 60;

const DEFAULT_MAX_ITERATIONS: Record<LoopMode, number> = {
  forEach: 100,
  repeatUntil: 5,
};

/** The server never runs more passes than this for one loop, whatever the node asks for. */
export const LOOP_MAX_ITERATIONS_CAP = 1000;

export const defaultMaxIterations = (mode: LoopMode | undefined): number =>
  DEFAULT_MAX_ITERATIONS[mode ?? DEFAULT_LOOP_MODE];

/**
 * The limit to carry over when the mode changes: a value the user set is kept, while the previous
 * mode's untouched default becomes the new mode's default (100 retries is rarely what is meant).
 */
export const maxIterationsForMode = (
  current: number | undefined,
  from: LoopMode,
  to: LoopMode
): number => (!current || current === defaultMaxIterations(from) ? defaultMaxIterations(to) : current);

/** A whole number of passes between 1 and the server cap, or the mode's default for anything else. */
export const normalizeMaxIterations = (raw: unknown, mode: LoopMode): number => {
  const parsed = Math.floor(Number(raw));
  if (!Number.isFinite(parsed) || parsed < 1) return defaultMaxIterations(mode);
  return Math.min(parsed, LOOP_MAX_ITERATIONS_CAP);
};

/** A whole number of at least `min`, or `fallback` for anything else. */
export const normalizeWholeNumber = (raw: unknown, min: number, fallback: number): number => {
  const parsed = Math.floor(Number(raw));
  return Number.isFinite(parsed) && parsed >= min ? parsed : fallback;
};

/** A number of seconds between 0 and `max` (fractions allowed), or 0 for anything else. */
export const normalizeSeconds = (raw: unknown, max = Number.POSITIVE_INFINITY): number => {
  const parsed = Number(raw);
  if (raw === "" || raw === null || raw === undefined || !Number.isFinite(parsed) || parsed <= 0) return 0;
  return Math.min(parsed, max);
};
