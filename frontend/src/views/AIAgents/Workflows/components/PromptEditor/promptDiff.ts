/** Prompts get heavier rewrites than config, so even low similarity reads as edit, not replacement */
export const PROMPT_MIN_SIMILARITY = 0.15;

/** Time limit on word diff (main thread). Timeout → fallback before/after blocks.
 *  Length ≠ cost (prose vs JSON differ); re-measure if typical prompts grow */
export const PROMPT_DIFF_TIMEOUT_MS = 400;
