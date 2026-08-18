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

  it("takes the preview from the first turn's message after sorting", () => {
    const groups = groupCasesByConversation([
      tc({
        id: "c2",
        source_conversation_id: "conv-1",
        turn_index: 1,
        input_data: { message: "second" },
      }),
      tc({
        id: "c1",
        source_conversation_id: "conv-1",
        turn_index: 0,
        input_data: { message: "first" },
      }),
    ]);
    expect(groups[0].preview).toBe("first");
  });

  it("falls back to JSON of input_data when the first turn has no string message", () => {
    const groups = groupCasesByConversation([
      tc({
        id: "c1",
        source_conversation_id: "conv-1",
        turn_index: 0,
        input_data: { foo: "bar" },
      }),
    ]);
    expect(groups[0].preview).toBe(JSON.stringify({ foo: "bar" }));
  });

  it("treats records without a source conversation as independent, keyed by id", () => {
    const groups = groupCasesByConversation([
      tc({ id: "x", input_data: { message: "hi" } }),
    ]);
    expect(groups).toHaveLength(1);
    expect(groups[0].conversationId).toBeNull();
    expect(groups[0].key).toBe("independent:x");
    expect(groups[0].preview).toBe("hi");
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

  it("orders imported conversations before independent records", () => {
    const groups = groupCasesByConversation([
      tc({ id: "i1", input_data: { message: "independent" } }),
      tc({ id: "c0", source_conversation_id: "conv-1", turn_index: 0 }),
    ]);
    expect(groups.map((g) => g.conversationId)).toEqual(["conv-1", null]);
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
