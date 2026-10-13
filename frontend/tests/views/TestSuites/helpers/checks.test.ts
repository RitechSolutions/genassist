import { describe, it, expect } from "vitest";
import {
  checkConversations,
  checkCounts,
  checkMissing,
  checkPlace,
  checkProblem,
  checkSentence,
  newCheck,
  parseChecks,
  serializeCheck,
  serializeChecks,
  targetFields,
} from "@/views/TestSuites/helpers/checks";
import type { TestCase } from "@/interfaces/testSuite.interface";
import type { EvaluationToolCatalog, ScenarioCheck } from "@/interfaces/testEvaluation.interface";

const turnCase = (id: string, conversation: string | null, turnIndex: number, message: string): TestCase => ({
  id,
  suite_id: "suite",
  input_data: { message },
  source_conversation_id: conversation,
  turn_index: turnIndex,
  created_at: "2026-01-01T00:00:00Z",
});

const CASES = [
  turnCase("a1", "conv-a", 0, "Hi"),
  turnCase("a2", "conv-a", 1, "I'm in London"),
  turnCase("m1", null, 0, "Standalone question"),
];
const conversations = checkConversations(CASES);

const CATALOG: EvaluationToolCatalog = {
  workflow_id: "wf",
  agents: [{ id: "agent-1", label: "Refund agent", type: "agentNode", workflow_path: [], tools: [
    { id: "tool-1", name: "save_region", label: "Save region", type: "toolBuilderNode" },
  ] }],
  routers: [{ id: "router-1", label: "Is allowed?", workflow_path: [], branches: [] }],
  action_nodes: [{ id: "step-1", label: "Create ticket", type: "zendeskTicketNode", workflow_path: [] }],
};

const check = (fields: Partial<ScenarioCheck> = {}): ScenarioCheck => ({
  id: "c1",
  expect: "should",
  kind: "reply_mentions",
  level: "every_conversation",
  when: "anywhere",
  text: "London",
  ...fields,
});

describe("checkConversations", () => {
  it("keys a conversation by its thread and a standalone turn by its case, as the run does", () => {
    expect(conversations.map((item) => item.key)).toEqual(["conv-a", "m1"]);
    expect(conversations[0].turns.map((turn) => [turn.caseId, turn.position, turn.message])).toEqual([
      ["a1", 1, "Hi"],
      ["a2", 2, "I'm in London"],
    ]);
  });
});

describe("checkSentence", () => {
  // The backend stores the same sentence with each result (test_scenario_checks.py).
  it.each([
    [{ level: "turn", case_id: "a2" }, 'The reply should mention "London".'],
    [{ level: "turn", case_id: "a2", expect: "should_not" }, 'The reply should not mention "London".'],
    [{ level: "conversation", conversation_id: "conv-a" }, 'At some point, the reply should mention "London".'],
    [{ level: "conversation", conversation_id: "conv-a", expect: "should_not" }, 'The reply should never mention "London".'],
    [{}, 'In every conversation, at some point, the reply should mention "London".'],
    [{ expect: "should_not" }, 'In every conversation, the reply should never mention "London".'],
    [{ when: "every_turn" }, 'On every turn, the reply should mention "London".'],
  ] as [Partial<ScenarioCheck>, string][])("reads %j as a sentence", (fields, sentence) => {
    expect(checkSentence(check(fields))).toBe(sentence);
  });

  it("reads every kind", () => {
    const turn = { level: "turn", case_id: "a2" } as const;
    expect(checkSentence(check({ ...turn, kind: "tool_called", tool_name: "save_region", agent_name: "Refund agent",
      args: { region: "united-kingdom" } }))).toBe('The tool "save_region" should be called by "Refund agent" with region = united-kingdom.');
    expect(checkSentence(check({ ...turn, kind: "step_runs", step_name: "Create ticket", expect: "should_not" })))
      .toBe('The step "Create ticket" should not run.');
    expect(checkSentence(check({ ...turn, kind: "route_taken", router_name: "Is allowed?", branch: "true" })))
      .toBe('The router "Is allowed?" should take "true".');
    expect(checkSentence(check({ ...turn, kind: "state_equals", key: "conversation_mode", value: "refund" })))
      .toBe('The remembered value "conversation_mode" should be "refund".');
    expect(checkSentence(check({ ...turn, kind: "reply_meets", rubric: "List all five regions" })))
      .toBe('The reply should do this: "List all five regions".');
    expect(checkSentence(check({ kind: "reply_meets", rubric: "Give a phone number", expect: "should_not" })))
      .toBe('In every conversation, the agent should never do this: "Give a phone number".');
  });
});

describe("checkMissing", () => {
  it("names what each kind still needs", () => {
    expect(checkMissing(check({ text: " " }))).toBe("Enter the words to look for.");
    expect(checkMissing(check({ kind: "reply_meets" }))).toBe("Write the rule.");
    expect(checkMissing(check({ kind: "tool_called" }))).toBe("Pick the tool.");
    expect(checkMissing(check({ kind: "step_runs" }))).toBe("Pick the step.");
    expect(checkMissing(check({ kind: "route_taken", router: "router-1" }))).toBe("Pick the branch.");
    expect(checkMissing(check({ kind: "state_equals", key: "mode" }))).toBe("Enter the value it should have.");
    expect(checkMissing(check({ level: "turn" }))).toBe("Pick the turn.");
    expect(checkMissing(check({ level: "conversation" }))).toBe("Pick the conversation.");
    expect(checkMissing(check())).toBeNull();
  });
});

describe("checkProblem", () => {
  it("finds a turn by case, then by conversation and position", () => {
    expect(checkProblem(check({ level: "turn", case_id: "a2" }), conversations)).toBeNull();
    expect(checkProblem(check({ level: "turn", case_id: "gone", conversation_id: "conv-a", turn_index: 1,
      turn_message: "I'm  in LONDON" }), conversations)).toBeNull();
  });

  it("flags a turn or conversation that is gone or changed", () => {
    expect(checkProblem(check({ level: "turn", case_id: "gone" }), conversations)).toBe(
      "This turn is no longer in the dataset.",
    );
    expect(checkProblem(check({ level: "turn", case_id: "gone", conversation_id: "conv-a", turn_index: 1,
      turn_message: "Something else" }), conversations)).toBe("This turn changed since the check was written.");
    expect(checkProblem(check({ level: "conversation", conversation_id: "gone" }), conversations)).toBe(
      "This conversation is no longer in the dataset.",
    );
  });

  it("flags a tool, step or router the workflow no longer has, matching names too", () => {
    expect(checkProblem(check({ kind: "tool_called", tool: "old-id", tool_name: "Save region" }), conversations, CATALOG)).toBeNull();
    expect(checkProblem(check({ kind: "tool_called", tool_name: "gone" }), conversations, CATALOG)).toBe(
      'The tool "gone" is not in this workflow.',
    );
    expect(checkProblem(check({ kind: "tool_called", tool: "tool-1", agent_name: "Other" }), conversations, CATALOG)).toBe(
      'The agent "Other" is not in this workflow.',
    );
    expect(checkProblem(check({ kind: "step_runs", step: "step-9", step_name: "Old" }), conversations, CATALOG)).toBe(
      'The step "Old" is not in this workflow.',
    );
    expect(checkProblem(check({ kind: "route_taken", router: "router-1", branch: "true" }), conversations, CATALOG)).toBeNull();
    expect(checkProblem(check({ kind: "step_runs", step: "gone" }), conversations)).toBeNull();
  });
});

describe("checkPlace", () => {
  it("names where a check applies", () => {
    expect(checkPlace(check(), conversations)).toBe("Every conversation");
    expect(checkPlace(check({ level: "conversation", conversation_id: "conv-a" }), conversations)).toBe("Hi");
    expect(checkPlace(check({ level: "turn", case_id: "a2" }), conversations)).toBe("Hi · Turn 2");
    expect(checkPlace(check({ level: "turn", case_id: "gone" }), conversations)).toBe("Removed turn");
  });
});

describe("new checks", () => {
  it("point at the conversation or turn they were added from", () => {
    const [conversation] = conversations;
    expect(targetFields({ level: "turn", conversation, turn: conversation.turns[1] })).toEqual({
      level: "turn", conversation_id: "conv-a", case_id: "a2", turn_index: 1, turn_message: "I'm in London",
    });
    const fresh = newCheck({ level: "conversation", conversation });
    expect(fresh).toMatchObject({ level: "conversation", conversation_id: "conv-a", case_id: null, expect: "should" });
    expect(fresh.id).toMatch(/^check-/);
  });
});

describe("saving and loading", () => {
  it("keeps only what the kind and level use, trimmed", () => {
    expect(serializeCheck(check({ text: " London ", tool: "left over", level: "turn", case_id: "a2",
      conversation_id: "conv-a", turn_index: 1, turn_message: "I'm in London", when: "every_turn" }))).toEqual({
      id: "c1", expect: "should", kind: "reply_mentions", level: "turn", when: "anywhere", text: "London",
      conversation_id: "conv-a", case_id: "a2", turn_index: 1, turn_message: "I'm in London",
    });
    expect(serializeCheck(check({ kind: "tool_called", tool: "tool-1", tool_name: "save_region",
      args: { region: " uk ", "": "dropped" } }))).toEqual({
      id: "c1", expect: "should", kind: "tool_called", level: "every_conversation", when: "anywhere",
      tool: "tool-1", tool_name: "save_region", args: { region: "uk" },
    });
  });

  it("stores the AI grader only when a check needs one", () => {
    expect(serializeChecks([check()], "provider-1")).toEqual({ checks: [serializeCheck(check())] });
    expect(serializeChecks([check({ kind: "reply_meets", rubric: "Greet" })], "provider-1")).toMatchObject({
      llm_provider_id: "provider-1",
    });
  });

  it("round-trips and drops entries that are not checks", () => {
    const saved = serializeChecks([check({ kind: "state_equals", key: "counter", value: "2" })], "");
    const { checks, providerId } = parseChecks({ ...saved, checks: [...(saved.checks as unknown[]), "junk", { id: "x", kind: "nope" }],
      llm_provider_id: "p" });
    expect(checks).toHaveLength(1);
    expect(checks[0]).toMatchObject({ kind: "state_equals", key: "counter", value: "2", level: "every_conversation" });
    expect(providerId).toBe("p");
    expect(parseChecks(undefined)).toEqual({ checks: [], providerId: "" });
  });
});

describe("checkCounts", () => {
  it("counts the checks on each conversation and each turn", () => {
    const every = check({ id: "every" });
    const whole = check({ id: "whole", level: "conversation", conversation_id: "conv-a" });
    const one = check({ id: "one", level: "turn", case_id: "a2" });
    const other = check({ id: "other", level: "turn", case_id: "a2", text: "Bye" });
    const gone = check({ id: "gone", level: "turn", case_id: "nope" });
    const counts = checkCounts([every, whole, one, other, gone], conversations);
    expect([...counts.byConversation]).toEqual([["conv-a", 1]]);
    expect([...counts.byTurn]).toEqual([["a2", 2]]);
  });
});
