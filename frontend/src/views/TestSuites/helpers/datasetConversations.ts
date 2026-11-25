import type { TestCase } from "@/interfaces/testSuite.interface";

/** Tag the backend stamps on cases created by conversation import. */
export const IMPORTED_TAG = "imported";

/** Tag the backend stamps on cases imported from a dataset file. */
export const FILE_IMPORTED_TAG = "imported-file";

/** Where a conversation's turns came from. */
export type ConversationOrigin = "conversation" | "file" | "manual";

export interface ConversationGroup {
  key: string;
  /** The replay thread. Null only for legacy records with no thread at all. */
  conversationId: string | null;
  /** Read from the tags, since hand-written threads carry a conversationId too. */
  origin: ConversationOrigin;
  cases: TestCase[];
}

const originOf = (entry: TestCase): ConversationOrigin => {
  if (entry.tags?.includes(IMPORTED_TAG)) return "conversation";
  if (entry.tags?.includes(FILE_IMPORTED_TAG)) return "file";
  return "manual";
};

/** When a conversation joined the dataset: its earliest turn. */
const addedAt = (group: ConversationGroup): number =>
  Math.min(
    ...group.cases.map((entry) =>
      entry.created_at ? Date.parse(entry.created_at) : 0,
    ),
  );

/**
 * Group records by source conversation, ordered by turn.
 *
 * Mirrors how evaluations replay a dataset: records sharing a conversation run as
 * one memory thread, and records without one are independent.
 */
export const groupCasesByConversation = (cases: TestCase[]): ConversationGroup[] => {
  const groups = new Map<string, ConversationGroup>();

  for (const entry of cases) {
    const conversationId = entry.source_conversation_id ?? null;
    const key = conversationId ?? `independent:${entry.id}`;
    const existing = groups.get(key);
    if (existing) {
      existing.cases.push(entry);
    } else {
      groups.set(key, {
        key,
        conversationId,
        origin: originOf(entry),
        cases: [entry],
      });
    }
  }

  const ordered = [...groups.values()];
  for (const group of ordered) {
    group.cases.sort((a, b) => (a.turn_index ?? 0) - (b.turn_index ?? 0));
  }

  // Oldest first, so a new conversation lands at the end rather than shuffling
  // the list. Sorting is stable, so same-timestamp groups keep their order.
  return ordered.sort((a, b) => addedAt(a) - addedAt(b));
};

export const countConversations = (cases: TestCase[]): number =>
  groupCasesByConversation(cases).length;

const LABEL_MAX_LENGTH = 60;

// The id a conversation goes by: its thread, or the case for a legacy single turn.
const shortIdOf = (group: ConversationGroup): string =>
  (group.conversationId ?? group.cases[0]?.id ?? "").slice(-6);

const openingMessage = (group: ConversationGroup): string => {
  const message = group.cases[0]?.input_data?.message;
  return typeof message === "string" ? message.replace(/\s+/g, " ").trim() : "";
};

const truncateAtWord = (text: string): string => {
  if (text.length <= LABEL_MAX_LENGTH) return text;
  // One character past the limit shows whether the cut falls between words.
  const head = text.slice(0, LABEL_MAX_LENGTH + 1);
  const lastSpace = head.lastIndexOf(" ");
  const cut = lastSpace > 0 ? head.slice(0, lastSpace) : text.slice(0, LABEL_MAX_LENGTH);
  return `${cut.trimEnd()}…`;
};

/** A name from an opening message, cut at a word, or the fallback without one. */
export const labelFromMessage = (message: string, fallback: string): string => {
  const text = message.replace(/\s+/g, " ").trim();
  return text ? truncateAtWord(text) : fallback;
};

/** A conversation's name: its opening user message, or its short id without one. */
export const conversationLabel = (group: ConversationGroup): string =>
  labelFromMessage(openingMessage(group), `Conversation #${shortIdOf(group)}`);

/** One label per conversation, keyed by group key. Clashing labels get the short id. */
export const conversationLabels = (groups: ConversationGroup[]): Map<string, string> => {
  const labelled = groups.map((group) => ({ group, label: conversationLabel(group) }));
  const counts = new Map<string, number>();
  labelled.forEach(({ label }) => counts.set(label, (counts.get(label) ?? 0) + 1));
  return new Map(
    labelled.map(({ group, label }) => [
      group.key,
      (counts.get(label) ?? 0) > 1 ? `${label} #${shortIdOf(group)}` : label,
    ]),
  );
};

/** Turns are named by position among the conversation's current turns. */
export const turnLabel = (position: number): string => `Turn ${position}`;

export interface PositionedTurn {
  entry: TestCase;
  /** 1-based position in the whole conversation. */
  position: number;
}

export interface ConversationMatch {
  group: ConversationGroup;
  turns: PositionedTurn[];
}

const turnMatches = (entry: TestCase, query: string): boolean =>
  JSON.stringify(entry.input_data ?? {}).toLowerCase().includes(query) ||
  JSON.stringify(entry.expected_output ?? {}).toLowerCase().includes(query);

/** Filters turns inside each conversation, so a matching turn keeps its position. */
export const searchConversations = (
  groups: ConversationGroup[],
  query: string,
): ConversationMatch[] => {
  const needle = query.trim().toLowerCase();
  return groups
    .map((group) => ({
      group,
      turns: group.cases
        .map((entry, index) => ({ entry, position: index + 1 }))
        .filter(({ entry }) => !needle || turnMatches(entry, needle)),
    }))
    .filter((match) => match.turns.length > 0);
};
