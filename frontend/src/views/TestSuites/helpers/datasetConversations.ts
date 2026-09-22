import type { TestCase } from "@/interfaces/testSuite.interface";

/** Tag the backend stamps on cases created by conversation import. */
export const IMPORTED_TAG = "imported";

export interface ConversationGroup {
  key: string;
  /** The replay thread. Null only for legacy records with no thread at all. */
  conversationId: string | null;
  /** True when these turns came from a real conversation rather than by hand.
   *  Hand-authored threads also carry a conversationId — it is what makes their
   *  turns replay as one memory thread — so the tag is what tells them apart. */
  isImported: boolean;
  cases: TestCase[];
}

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
        isImported: !!entry.tags?.includes(IMPORTED_TAG),
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
