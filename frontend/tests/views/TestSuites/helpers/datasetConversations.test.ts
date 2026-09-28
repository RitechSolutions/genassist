import { describe, expect, it } from "vitest";
import {
  groupCasesByConversation,
  countConversations,
} from "@/views/TestSuites/helpers/datasetConversations";
import type { TestCase } from "@/interfaces/testSuite.interface";

const tc = (overrides: Partial<TestCase>): TestCase => ({
  suite_id: "suite",
  input_data: {},
  ...overrides,
});

describe("groupCasesByConversation", () => {
  it("returns an empty array for no cases", () => {
    expect(groupCasesByConversation([])).toEqual([]);
  });

  it("groups cases sharing a source conversation, ordered by turn_index", () => {
    const groups = groupCasesByConversation([
      tc({ id: "c2", source_conversation_id: "conv-1", turn_index: 1 }),
      tc({ id: "c1", source_conversation_id: "conv-1", turn_index: 0 }),
    ]);
    expect(groups).toHaveLength(1);
    expect(groups[0].conversationId).toBe("conv-1");
    expect(groups[0].key).toBe("conv-1");
    expect(groups[0].cases.map((c) => c.id)).toEqual(["c1", "c2"]);
  });



  it("treats records without a source conversation as independent, keyed by id", () => {
    const groups = groupCasesByConversation([
      tc({ id: "x", input_data: { message: "hi" } }),
    ]);
    expect(groups).toHaveLength(1);
    expect(groups[0].conversationId).toBeNull();
    expect(groups[0].key).toBe("independent:x");
  });

  it("keeps separate independent records in their own groups", () => {
    const groups = groupCasesByConversation([
      tc({ id: "a" }),
      tc({ id: "b" }),
    ]);
    expect(groups).toHaveLength(2);
    expect(groups.map((g) => g.key).sort()).toEqual([
      "independent:a",
      "independent:b",
    ]);
  });

  it("orders conversations by when they joined the dataset, not by source", () => {
    const groups = groupCasesByConversation([
      tc({
        id: "c0",
        source_conversation_id: "conv-1",
        turn_index: 0,
        tags: ["imported"],
        created_at: "2026-09-02T10:00:00Z",
      }),
      tc({
        id: "m0",
        source_conversation_id: "thread-1",
        turn_index: 0,
        created_at: "2026-09-01T10:00:00Z",
      }),
    ]);
    // The hand-authored thread was added first, so it stays first.
    expect(groups.map((g) => g.conversationId)).toEqual(["thread-1", "conv-1"]);
  });

  it("uses a conversation's earliest turn, so a later turn does not move it", () => {
    const groups = groupCasesByConversation([
      tc({
        id: "b0",
        source_conversation_id: "thread-2",
        turn_index: 0,
        created_at: "2026-09-02T10:00:00Z",
      }),
      tc({
        id: "a0",
        source_conversation_id: "thread-1",
        turn_index: 0,
        created_at: "2026-09-01T10:00:00Z",
      }),
      // Appended to thread-1 long after thread-2 was created.
      tc({
        id: "a1",
        source_conversation_id: "thread-1",
        turn_index: 1,
        created_at: "2026-09-03T10:00:00Z",
      }),
    ]);
    expect(groups.map((g) => g.conversationId)).toEqual(["thread-1", "thread-2"]);
  });

  it("marks a group imported only when its cases carry the imported tag", () => {
    const groups = groupCasesByConversation([
      tc({
        id: "c0",
        source_conversation_id: "conv-1",
        turn_index: 0,
        tags: ["imported"],
      }),
      // A hand-authored thread also has a conversation id — that is what makes
      // its turns replay together — so only the tag tells the two apart.
      tc({ id: "m0", source_conversation_id: "thread-1", turn_index: 0 }),
    ]);
    expect(groups.map((g) => g.isImported)).toEqual([true, false]);
  });

  it("does not hoist imported conversations above hand-authored ones", () => {
    const groups = groupCasesByConversation([
      tc({ id: "m0", source_conversation_id: "thread-1", turn_index: 0 }),
      tc({
        id: "c0",
        source_conversation_id: "conv-1",
        turn_index: 0,
        tags: ["imported"],
      }),
      tc({ id: "m1", source_conversation_id: "thread-2", turn_index: 0 }),
    ]);
    // No timestamps, so insertion order holds for all three.
    expect(groups.map((g) => g.conversationId)).toEqual([
      "thread-1",
      "conv-1",
      "thread-2",
    ]);
    expect(groups.map((g) => g.isImported)).toEqual([false, true, false]);
  });

  it("keeps a hand-authored thread's turns in one group, ordered by turn", () => {
    const groups = groupCasesByConversation([
      tc({ id: "m1", source_conversation_id: "thread-1", turn_index: 1 }),
      tc({ id: "m0", source_conversation_id: "thread-1", turn_index: 0 }),
    ]);
    expect(groups).toHaveLength(1);
    expect(groups[0].isImported).toBe(false);
    expect(groups[0].cases.map((c) => c.id)).toEqual(["m0", "m1"]);
  });

  it("defaults a missing turn_index to 0 for ordering", () => {
    const groups = groupCasesByConversation([
      tc({ id: "c2", source_conversation_id: "conv-1", turn_index: 2 }),
      tc({ id: "cUndef", source_conversation_id: "conv-1" }),
    ]);
    // The record with no turn_index sorts as 0, ahead of turn_index 2.
    expect(groups[0].cases.map((c) => c.id)).toEqual(["cUndef", "c2"]);
  });
});

describe("countConversations", () => {
  it("counts the number of distinct conversation groups", () => {
    expect(
      countConversations([
        tc({ id: "c0", source_conversation_id: "conv-1", turn_index: 0 }),
        tc({ id: "c1", source_conversation_id: "conv-1", turn_index: 1 }),
        tc({ id: "x" }),
      ]),
    ).toBe(2);
  });

  it("returns 0 for no cases", () => {
    expect(countConversations([])).toBe(0);
  });
});
