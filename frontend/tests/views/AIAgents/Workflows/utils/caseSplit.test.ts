import { describe, expect, it } from "vitest";
import type { CaseRow } from "@/views/AIAgents/Workflows/utils/promptEditorRuns";
import {
  DEFAULT_HOLDOUT_SHARE,
  splitCasesByConversation,
} from "@/views/AIAgents/Workflows/utils/caseSplit";

const caseRow = (id: string, conversationId: string | null = null, turn = 0): CaseRow => ({
  id,
  input_data: { message: id },
  expected_output: null,
  source_conversation_id: conversationId,
  turn_index: conversationId ? turn : null,
});

const suiteOf = (sizes: readonly number[]): CaseRow[] =>
  sizes.flatMap((size, group) =>
    size === 1
      ? [caseRow(`g${group}-solo`)]
      : Array.from({ length: size }, (_, turn) =>
          caseRow(`g${group}-t${turn}`, `conv-${group}`, turn),
        ),
  );

const sizeOf = (result: { dev: CaseRow[]; holdout: CaseRow[] }) => [
  result.holdout.length,
  result.dev.length,
];

const idsOf = (rows: CaseRow[]) => rows.map((row) => row.id).sort();

describe("splitCasesByConversation", () => {
  it("holds out half the cases of an evenly split suite", () => {
    expect(sizeOf(splitCasesByConversation(suiteOf(Array(20).fill(1))))).toEqual([10, 10]);
  });

  it("splits four single-case groups two and two", () => {
    expect(sizeOf(splitCasesByConversation(suiteOf([1, 1, 1, 1])))).toEqual([2, 2]);
  });

  it("stops at the hold-out cap rather than the share", () => {
    expect(sizeOf(splitCasesByConversation(suiteOf(Array(100).fill(1))))).toEqual([25, 75]);
  });

  it("is infeasible below four groups, and says so", () => {
    const result = splitCasesByConversation(suiteOf([1, 1, 1]));

    expect(result.feasible).toBe(false);
    expect(result.holdout).toEqual([]);
    expect(result.reason).toBe("Needs at least four conversations or cases.");
  });

  it("is infeasible when no two groups fit the cap", () => {
    const result = splitCasesByConversation(suiteOf([30, 30, 30, 30]));

    expect(result.feasible).toBe(false);
    expect(result.reason).toBe(
      "The shortest conversations do not fit a 25-case hold-out.",
    );
  });

  it("never splits a conversation across the two sides", () => {
    const result = splitCasesByConversation(suiteOf([3, 3, 3, 3]));
    const conversationOf = (rows: CaseRow[]) =>
      new Set(rows.map((row) => row.source_conversation_id));
    const held = conversationOf(result.holdout);

    expect(result.feasible).toBe(true);
    expect([...conversationOf(result.dev)].some((id) => held.has(id))).toBe(false);
  });

  it("keeps a group too large to hold out whole in development", () => {
    const result = splitCasesByConversation(suiteOf([30, 1, 1, 1]));

    expect(sizeOf(result)).toEqual([2, 31]);
    expect(result.dev.filter((row) => row.source_conversation_id === "conv-0")).toHaveLength(30);
  });

  it("takes the short groups when the largest would exhaust the budget", () => {
    const result = splitCasesByConversation(suiteOf([1, 1, 1, 25]));

    expect(result.feasible).toBe(true);
    expect(sizeOf(result)).toEqual([2, 26]);
  });

  it("fills the quota exactly when a large and a small group add up to it", () => {
    expect(sizeOf(splitCasesByConversation(suiteOf([12, 12, 1, 1])))).toEqual([13, 13]);
  });

  it("partitions a shuffled suite identically", () => {
    const cases = suiteOf([4, 4, 2, 2, 1, 1]);
    const shuffled = [...cases].reverse();

    expect(idsOf(splitCasesByConversation(shuffled).holdout)).toEqual(
      idsOf(splitCasesByConversation(cases).holdout),
    );
  });

  it("does not track the order the cases were created in", () => {
    const suite = suiteOf([2, 2, 2, 2]);
    const recreatedLater = suite.map((row, index) => ({
      ...row,
      id: `z-later-${suite.length - index}`,
    }));
    const heldConversations = (rows: CaseRow[]) =>
      new Set(rows.map((row) => row.source_conversation_id));

    expect(heldConversations(splitCasesByConversation(recreatedLater).holdout)).toEqual(
      heldConversations(splitCasesByConversation(suite).holdout),
    );
  });

  it("groups by a normalised key, so a conversation is never counted twice", () => {
    const cases = [
      caseRow("a", "conv-1", 0),
      caseRow("b", "conv-1", 1),
      caseRow("c"),
      caseRow("d"),
      caseRow("e"),
    ];

    expect(splitCasesByConversation(cases).groups).toBe(4);
  });

  it("holds the share at a half", () => {
    expect(DEFAULT_HOLDOUT_SHARE).toBe(0.5);
  });
});
