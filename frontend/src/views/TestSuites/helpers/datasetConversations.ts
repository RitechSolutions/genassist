import type { TestCase } from "@/interfaces/testSuite.interface";

export interface ConversationGroup {
  key: string;
  /** Null for manual and legacy records, which replay independently. */
  conversationId: string | null;
  cases: TestCase[];
  /** First turn's message, used to make the conversation recognisable. */
  preview: string;
}

const previewOf = (entry: TestCase): string => {
  const message = (entry.input_data as Record<string, unknown>)?.message;
  return typeof message === "string" ? message : JSON.stringify(entry.input_data ?? {});
};

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
      groups.set(key, { key, conversationId, cases: [entry], preview: "" });
    }
  }

  const ordered = [...groups.values()];
  for (const group of ordered) {
    group.cases.sort((a, b) => (a.turn_index ?? 0) - (b.turn_index ?? 0));
    group.preview = previewOf(group.cases[0]);
  }

  // Imported conversations first; independent records trail behind them.
  return ordered.sort((a, b) => {
    if (!!a.conversationId === !!b.conversationId) return 0;
    return a.conversationId ? -1 : 1;
  });
};

export const countConversations = (cases: TestCase[]): number =>
  groupCasesByConversation(cases).length;
