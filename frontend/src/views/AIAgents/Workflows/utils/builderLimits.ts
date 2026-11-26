/**
 * Longest message the Workflow Builder accepts, in characters (about 2,000 tokens).
 *
 * A message is re-sent on every model call of its turn and then sits in the
 * conversation history for the next ten turns, so an unbounded paste is the one
 * thing that can make a single turn arbitrarily expensive. The cap still leaves
 * room for a full agent brief or a pasted policy page.
 */
export const BUILDER_MESSAGE_MAX_CHARS = 8000;
