import { describe, expect, it } from "vitest";
import {
  caseLabel,
  conversationLabel,
  conversationLabels,
  groupCasesByConversation,
  countConversations,
  indexConversations,
  ruleConversations,
  ruleTargetLabel,
  searchConversations,
} from "@/views/TestSuites/helpers/datasetConversations";
import type { TestCase } from "@/interfaces/testSuite.interface";
import type { TestToolRuleResult } from "@/interfaces/testEvaluation.interface";

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
    expect(groups.map((g) => g.origin)).toEqual(["conversation", "manual"]);
  });

  it("marks a group imported from a file by its own tag", () => {
    const groups = groupCasesByConversation([
      tc({
        id: "f0",
        source_conversation_id: "file-1",
        turn_index: 0,
        tags: ["refund", "imported-file"],
      }),
    ]);
    expect(groups[0].origin).toBe("file");
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
    expect(groups.map((g) => g.origin)).toEqual(["manual", "conversation", "manual"]);
  });

  it("keeps a hand-authored thread's turns in one group, ordered by turn", () => {
    const groups = groupCasesByConversation([
      tc({ id: "m1", source_conversation_id: "thread-1", turn_index: 1 }),
      tc({ id: "m0", source_conversation_id: "thread-1", turn_index: 0 }),
    ]);
    expect(groups).toHaveLength(1);
    expect(groups[0].origin).toBe("manual");
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

const turn = (
  id: string,
  conversationId: string | null,
  turnIndex: number,
  message?: string,
  expected?: string,
): TestCase =>
  tc({
    id,
    source_conversation_id: conversationId,
    turn_index: turnIndex,
    input_data: message === undefined ? {} : { message },
    ...(expected === undefined ? {} : { expected_output: { value: expected } }),
  });

const onlyGroup = (cases: TestCase[]) => groupCasesByConversation(cases)[0];

describe("conversationLabel", () => {
  it("uses the earliest turn's user message", () => {
    const group = onlyGroup([
      turn("c2", "conv-1", 1, "And for refunds?"),
      turn("c1", "conv-1", 0, "How do I reset my password?"),
    ]);
    expect(conversationLabel(group)).toBe("How do I reset my password?");
  });

  it("collapses whitespace", () => {
    const group = onlyGroup([turn("c1", "conv-1", 0, "  Hello\n\n  there\tfriend  ")]);
    expect(conversationLabel(group)).toBe("Hello there friend");
  });

  it("cuts a long message at 60 characters on a word boundary", () => {
    const message =
      "I ordered a pair of running shoes last week and the parcel never arrived at my door";
    const label = conversationLabel(onlyGroup([turn("c1", "conv-1", 0, message)]));
    expect(label).toBe("I ordered a pair of running shoes last week and the parcel…");
    expect(label.length - 1).toBeLessThanOrEqual(60);
  });

  it("keeps a word that ends exactly at the limit", () => {
    const message = `${"a".repeat(59)}b and more`;
    expect(conversationLabel(onlyGroup([turn("c1", "conv-1", 0, message)]))).toBe(
      `${"a".repeat(59)}b…`,
    );
  });

  it("hard-cuts a single word longer than the limit", () => {
    const message = "x".repeat(80);
    expect(conversationLabel(onlyGroup([turn("c1", "conv-1", 0, message)]))).toBe(
      `${"x".repeat(60)}…`,
    );
  });

  it("leaves a message of exactly 60 characters whole", () => {
    const message = "y".repeat(60);
    expect(conversationLabel(onlyGroup([turn("c1", "conv-1", 0, message)]))).toBe(message);
  });

  it("falls back to the conversation's short id without a text message", () => {
    const group = onlyGroup([
      tc({ id: "c1", source_conversation_id: "thread-abc123", turn_index: 0, input_data: { q: 1 } }),
    ]);
    expect(conversationLabel(group)).toBe("Conversation #abc123");
    expect(conversationLabel(onlyGroup([turn("c1", "thread-9z9z9z", 0, "   ")]))).toBe(
      "Conversation #9z9z9z",
    );
  });

  it("uses the case id for a legacy turn with no conversation", () => {
    expect(conversationLabel(onlyGroup([turn("case-0f0f0f", null, 0)]))).toBe(
      "Conversation #0f0f0f",
    );
  });
});

describe("conversationLabels", () => {
  it("appends the short id only to labels that clash", () => {
    const groups = groupCasesByConversation([
      turn("a0", "thread-aaaaaa", 0, "Hi"),
      turn("b0", "thread-bbbbbb", 0, "Hi"),
      turn("c0", "thread-cccccc", 0, "Where is my order?"),
    ]);
    const labels = conversationLabels(groups);
    expect(labels.get("thread-aaaaaa")).toBe("Hi #aaaaaa");
    expect(labels.get("thread-bbbbbb")).toBe("Hi #bbbbbb");
    expect(labels.get("thread-cccccc")).toBe("Where is my order?");
  });
});

describe("searchConversations", () => {
  const cases = [
    turn("a0", "conv-a", 0, "Hello", "Hi there"),
    turn("a1", "conv-a", 1, "Refund please", "Sure"),
    turn("a2", "conv-a", 2, "Thanks", "Bye"),
    turn("b0", "conv-b", 0, "Track my parcel", "It ships today"),
  ];
  const groups = groupCasesByConversation(cases);

  it("shows every turn, numbered by position, without a query", () => {
    const matches = searchConversations(groups, "  ");
    expect(matches).toHaveLength(2);
    expect(matches[0].turns.map((t) => [t.entry.id, t.position])).toEqual([
      ["a0", 1],
      ["a1", 2],
      ["a2", 3],
    ]);
  });

  it("keeps a matching turn's position in the whole conversation", () => {
    const matches = searchConversations(groups, "REFUND");
    expect(matches).toHaveLength(1);
    expect(matches[0].group.cases).toHaveLength(3);
    expect(matches[0].turns.map((t) => [t.entry.id, t.position])).toEqual([["a1", 2]]);
  });

  it("matches the expected reply too", () => {
    const matches = searchConversations(groups, "ships today");
    expect(matches.map((m) => m.group.key)).toEqual(["conv-b"]);
  });

  it("drops conversations with no matching turn", () => {
    expect(searchConversations(groups, "nothing like this")).toEqual([]);
  });
});

describe("ruleConversations", () => {
  it("labels conversations like the dataset page and turns by position", () => {
    const conversations = ruleConversations([
      turn("a1", "conv-a", 4, "Second"),
      turn("a0", "conv-a", 2, "Where is my order?"),
      turn("b0", "conv-b", 0, "Hello"),
    ]);
    expect(conversations.map((c) => c.label)).toEqual([
      "Where is my order? (2 turns)",
      "Hello (1 turn)",
    ]);
    // Labels follow position; the targeted value stays the stored turn_index.
    expect(conversations[0].turns).toEqual([
      { caseId: "a0", turnIndex: 2, label: "Turn 1" },
      { caseId: "a1", turnIndex: 4, label: "Turn 2" },
    ]);
  });

  it("leaves out legacy turns that have no conversation to target", () => {
    expect(ruleConversations([turn("x", null, 0, "Hi")])).toEqual([]);
  });
});

describe("indexConversations", () => {
  const cases = [
    turn("a0", "conv-a", 3, "Where is my order?"),
    turn("a1", "conv-a", 7, "Thanks"),
    turn("legacy-123456", null, 0, "Single question"),
  ];
  const index = indexConversations(cases);

  it("names a case by its conversation and its turn position", () => {
    expect(caseLabel(index, "a1")).toBe("Where is my order? · Turn 2");
    expect(caseLabel(index, "legacy-123456")).toBe("Single question · Turn 1");
  });

  it("keeps a short id for a case no longer in the dataset", () => {
    expect(caseLabel(index, "gone-abcd")).toBe("Case #abcd");
  });

  it("names rule results by the dataset rather than the stored turn index", () => {
    const rule = (overrides: Partial<TestToolRuleResult>): TestToolRuleResult => ({
      id: "r",
      run_id: "run",
      technique: "tool_used",
      rule_id: "rule-1",
      scope: "every_turn",
      status: "passed",
      created_at: "",
      ...overrides,
    });
    expect(ruleTargetLabel(rule({ case_id: "a1" }), index)).toBe("Turn 2");
    expect(
      ruleTargetLabel(rule({ scope: "conversation", source_conversation_id: "conv-a" }), index),
    ).toBe("Where is my order? · 2 turns");
    expect(ruleTargetLabel(rule({ case_id: "gone" }), index)).toBeNull();
  });
});
