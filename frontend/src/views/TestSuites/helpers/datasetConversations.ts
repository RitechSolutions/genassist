import type { TestCase } from "@/interfaces/testSuite.interface";
import type {
  RuleConversation,
  TestToolRuleResult,
} from "@/interfaces/testEvaluation.interface";

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

const turnsLabel = (count: number): string => `${count} turn${count === 1 ? "" : "s"}`;

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

/** A conversation's name: its opening user message, or its short id without one. */
export const conversationLabel = (group: ConversationGroup): string => {
  const message = openingMessage(group);
  return message ? truncateAtWord(message) : `Conversation #${shortIdOf(group)}`;
};

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

/** Conversations a specific-turn rule can target. The targeted value stays turn_index. */
export const ruleConversations = (cases: TestCase[]): RuleConversation[] => {
  const groups = groupCasesByConversation(cases);
  const labels = conversationLabels(groups);
  return groups
    .filter((group) => group.conversationId)
    .map((group) => ({
      id: group.conversationId as string,
      label: `${labels.get(group.key)} (${turnsLabel(group.cases.length)})`,
      turns: group.cases.map((turn, index) => ({
        caseId: turn.id as string,
        turnIndex: turn.turn_index ?? 0,
        label: turnLabel(index + 1),
      })),
    }));
};

export interface ConversationIndex {
  /** Case id to its conversation's label and turn position. */
  turns: Map<string, { conversation: string; position: number }>;
  /** Conversation id to its label and current turn count. */
  conversations: Map<string, { label: string; turnCount: number }>;
}

/** Names for a dataset's turns and conversations, as the dataset page shows them. */
export const indexConversations = (cases: TestCase[]): ConversationIndex => {
  const groups = groupCasesByConversation(cases);
  const labels = conversationLabels(groups);
  const index: ConversationIndex = { turns: new Map(), conversations: new Map() };
  for (const group of groups) {
    const label = labels.get(group.key) ?? conversationLabel(group);
    if (group.conversationId) {
      index.conversations.set(group.conversationId, { label, turnCount: group.cases.length });
    }
    group.cases.forEach((entry, position) => {
      if (entry.id) index.turns.set(entry.id, { conversation: label, position: position + 1 });
    });
  }
  return index;
};

/** "{conversation} · Turn {position}". A case no longer in the dataset keeps its short id. */
export const caseLabel = (index: ConversationIndex, caseId: string | null | undefined): string => {
  const turn = caseId ? index.turns.get(caseId) : undefined;
  if (turn) return `${turn.conversation} · ${turnLabel(turn.position)}`;
  return `Case #${(caseId ?? "").slice(-4)}`;
};

/** What a rule result graded, named from the dataset. Null when the dataset lacks it. */
export const ruleTargetLabel = (
  result: TestToolRuleResult,
  index: ConversationIndex,
): string | null => {
  if (result.scope === "conversation") {
    const conversation = result.source_conversation_id
      ? index.conversations.get(result.source_conversation_id)
      : undefined;
    return conversation ? `${conversation.label} · ${turnsLabel(conversation.turnCount)}` : null;
  }
  const turn = result.case_id ? index.turns.get(result.case_id) : undefined;
  return turn ? turnLabel(turn.position) : null;
};
