import { describe, it, expect } from "vitest";
import {
  checkConversations,
  checkMissing,
  checkPlace,
  checkProblem,
  checkSentence,
  conversationSentence,
  turnFact,
  chosenConversations,
  goneNote,
  isAiGraded,
  leftOutNote,
  stepTypeLabel,
  needsConversion,
  newCheck,
  parseChecks,
  retarget,
  serializeCheck,
  serializeChecks,
  targetFields,
  targetOf,
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
  it("carries each turn's expected reply and its other inputs as text", () => {
    const [conversation] = checkConversations([
      {
        ...turnCase("b1", "conv-b", 0, "Bonjour"),
        input_data: { message: "Bonjour", region: "france", flags: { vip: true } },
        expected_output: { value: "Bonjour !" },
      },
      { ...turnCase("b2", "conv-b", 1, "Merci"), expected_output: { status: "closed", code: 2 } },
    ]);
    expect(conversation.turns[0].expected).toBe("Bonjour !");
    expect(conversation.turns[0].inputs).toEqual([
      ["region", "france"],
      ["flags", '{"vip":true}'],
    ]);
    expect(conversation.turns[1].expected).toBe('{"status":"closed","code":2}');
    expect(conversation.turns[1].inputs).toEqual([]);
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
    [{ level: "conversation", conversation_ids: ["conv-a", "m1"] }, 'At some point, the reply should mention "London".'],
    [{ level: "conversation", conversation_ids: ["conv-a"], when: "every_turn" }, 'On every turn, the reply should mention "London".'],
    [
      { level: "conversation", conversation_ids: ["conv-a"], when: "every_turn", expect: "should_not" },
      'On every turn, the reply should not mention "London".',
    ],
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

describe("conversationSentence", () => {
  it.each([
    [{ expect: "should_not" }, 'No reply should mention "London".'],
    [{ when: "every_turn" }, 'Every reply should mention "London".'],
    [{ when: "every_turn", expect: "should_not" }, 'No reply should mention "London".'],
    [{}, 'At least one reply should mention "London".'],
    [{ kind: "step_runs", step_name: "Hand-over reply", expect: "should_not" }, 'The step "Hand-over reply" should never run.'],
    [{ kind: "route_taken", router_name: "Wants a person?", branch: "true" }, 'At least once, the router "Wants a person?" should take "true".'],
    [{ kind: "step_fails", expect: "should_not" }, "No step should ever fail."],
    [{ kind: "reply_matches", match: "exact" }, "Every reply should be exactly the expected reply."],
    [{ kind: "tool_called", tool_name: "refund", max_calls: 2 }, 'The tool "refund" should be called at most 2 times.'],
    [{ kind: "reply_meets", rubric: "Be polite" }, 'The agent should do this: "Be polite".'],
    // A quote that ends its own sentence takes no second full stop.
    [{ kind: "reply_meets", rubric: "Be polite.", when: "every_turn" }, 'Every reply should do this: "Be polite."'],
  ] as [Partial<ScenarioCheck>, string][])("says %j without the conversation", (fields, sentence) => {
    expect(conversationSentence(check(fields))).toBe(sentence);
  });
});

describe("turnFact", () => {
  it("says what happened on one reply, from the check", () => {
    expect(turnFact(check({ expect: "should_not" }), false)).toBe('The reply did not mention "London".');
    expect(turnFact(check({}), true)).toBe('The reply mentioned "London".');
    expect(turnFact(check({ kind: "step_runs", step_name: "Hand-over reply" }), false)).toBe('The step "Hand-over reply" did not run.');
    expect(turnFact(check({ kind: "state_equals", key: "mode", value: "refund" }), true)).toBe('mode was "refund".');
    expect(turnFact(check({ kind: "step_fails" }), false)).toBe("No step failed.");
    expect(turnFact(check({ kind: "reply_meets", rubric: "Be polite" }), true)).toBeNull();
  });
});

describe("checkMissing", () => {
  it("names what each kind still needs", () => {
    expect(checkMissing(check({ text: " " }))).toBe("Enter the words to look for.");
    expect(checkMissing(check({ kind: "reply_meets" }))).toBe("Write the rule.");
    expect(checkMissing(check({ kind: "tool_called" }))).toBe("Pick the tool.");
    expect(checkMissing(check({ kind: "tool_called", tool: "t1", tools: [{}] }))).toBe("Pick each tool.");
    // A Should not reads only its own tool, so an empty other row left from Should does not count.
    expect(checkMissing(check({ kind: "tool_called", expect: "should_not", tool: "t1", tools: [{}] }))).toBeNull();
    expect(checkMissing(check({ kind: "step_runs" }))).toBe("Pick the step.");
    expect(checkMissing(check({ kind: "route_taken", router: "router-1" }))).toBe("Pick the branch.");
    expect(checkMissing(check({ kind: "state_equals", key: "mode" }))).toBe("Enter the value it should have.");
    expect(checkMissing(check({ level: "turn" }))).toBe("Pick the turn.");
    expect(checkMissing(check({ level: "conversation" }))).toBe("Choose the conversations.");
    expect(checkMissing(check({ level: "conversation", conversation_ids: ["conv-a"] }))).toBeNull();
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
      "This turn is no longer in the dataset. It will not be graded until you fix it.",
    );
    expect(checkProblem(check({ level: "turn", case_id: "gone", conversation_id: "conv-a", turn_index: 1,
      turn_message: "Something else" }), conversations)).toBe(
      "This turn changed since the check was written. It will not be graded until you fix it.",
    );
    expect(checkProblem(check({ level: "conversation", conversation_id: "gone" }), conversations)).toBe(
      "This conversation is no longer in the dataset. It will not be graded until you fix it.",
    );
  });

  it("flags a tool, step or router the workflow no longer has, matching names too", () => {
    expect(checkProblem(check({ kind: "tool_called", tool: "old-id", tool_name: "Save region" }), conversations, CATALOG)).toBeNull();
    // What the workflow lacks cannot happen, so the check is still graded, as the older rules were.
    expect(checkProblem(check({ kind: "tool_called", tool_name: "gone" }), conversations, CATALOG)).toBe(
      'The tool "gone" is not in this workflow, so it can never be called.',
    );
    expect(checkProblem(check({ kind: "tool_called", tool: "tool-1", agent_name: "Other" }), conversations, CATALOG)).toBe(
      'The agent "Other" is not in this workflow. It will not be graded until you fix it.',
    );
    expect(checkProblem(check({ kind: "step_runs", step: "step-9", step_name: "Old" }), conversations, CATALOG)).toBe(
      'The step "Old" is not in this workflow, so it can never run.',
    );
    expect(checkProblem(check({ kind: "route_taken", router: "router-1", branch: "true" }), conversations, CATALOG)).toBeNull();
    expect(checkProblem(check({ kind: "step_runs", step: "gone" }), conversations)).toBeNull();
  });
});

describe("checkPlace", () => {
  it("names where a check applies", () => {
    expect(checkPlace(check(), conversations)).toBe("All conversations");
    expect(checkPlace(check({ level: "conversation", conversation_id: "conv-a" }), conversations)).toBe('"Hi"');
    expect(checkPlace(check({ level: "conversation", conversation_ids: ["conv-a", "gone"] }), conversations)).toBe(
      '"Hi" and a removed conversation',
    );
    expect(
      checkPlace(check({ level: "conversation", conversation_ids: ["conv-a", "m1", "gone"] }), conversations),
    ).toBe('"Hi", "Standalone question" and 1 more');
    expect(checkPlace(check({ level: "turn", case_id: "a2" }), conversations)).toBe("Hi · Turn 2");
    expect(checkPlace(check({ level: "turn", case_id: "gone" }), conversations)).toBe("Removed turn");
  });
});

describe("new checks", () => {
  it("point at the chosen conversations or the picked turn", () => {
    const [conversation, standalone] = conversations;
    expect(targetFields({ level: "turn", conversation, turn: conversation.turns[1] })).toEqual({
      level: "turn", conversation_ids: null, conversation_id: "conv-a", case_id: "a2", turn_index: 1,
      turn_message: "I'm in London",
    });
    expect(targetFields({ level: "conversation", conversations: [conversation, standalone] })).toEqual({
      level: "conversation", conversation_ids: ["conv-a", "m1"], conversation_id: null, case_id: null,
      turn_index: null, turn_message: null,
    });
    const fresh = newCheck();
    expect(fresh).toMatchObject({ level: "every_conversation", conversation_ids: null, case_id: null, expect: "should" });
    expect(fresh.id).toMatch(/^check-/);
  });
});

describe("changing where a check applies", () => {
  it("keeps a picked turn's conversation when it applies to chosen conversations", () => {
    const turn = check({ level: "turn", case_id: "a2", conversation_id: "conv-a", turn_index: 1 });
    expect(retarget(turn, "conversation", conversations)).toMatchObject({
      level: "conversation", conversation_ids: ["conv-a"], case_id: null,
    });
    expect(retarget(turn, "every_conversation", conversations)).toMatchObject({ level: "every_conversation", case_id: null });
  });

  it("gives back what was picked for a place when it is chosen again", () => {
    const chosen = check({ level: "conversation", conversation_ids: ["conv-a", "m1"] });
    const remembered = targetOf(chosen);
    const all = { ...chosen, ...retarget(chosen, "every_conversation", conversations) } as ScenarioCheck;
    expect(retarget(all, "conversation", conversations, remembered)).toMatchObject({
      level: "conversation", conversation_ids: ["conv-a", "m1"],
    });
    const turn = check({ level: "turn", case_id: "a2", conversation_id: "conv-a", turn_index: 1, turn_message: "x" });
    const back = retarget(chosen, "turn", conversations, targetOf(turn));
    expect(back).toMatchObject({ level: "turn", case_id: "a2", conversation_id: "conv-a", turn_index: 1 });
  });
});

describe("chosen conversations", () => {
  it("read one stored the older way as chosen", () => {
    expect(chosenConversations(check({ level: "conversation", conversation_id: "conv-a" }))).toEqual(["conv-a"]);
    expect(chosenConversations(check({ level: "conversation", conversation_ids: ["m1", "m1"], conversation_id: "conv-a" })))
      .toEqual(["m1", "conv-a"]);
    expect(chosenConversations(check({ conversation_ids: ["m1"] }))).toEqual([]);
  });

  it("are saved as a list, and the older field loads into it", () => {
    expect(serializeCheck(check({ level: "conversation", conversation_ids: ["conv-a", " "], conversation_id: "m1",
      when: "every_turn" }))).toEqual({
      id: "c1", expect: "should", kind: "reply_mentions", level: "conversation", when: "every_turn",
      conversation_ids: ["conv-a", "m1"], text: "London",
    });
    const { checks } = parseChecks({ checks: [{ id: "a", kind: "reply_mentions", text: "x", level: "conversation",
      conversation_id: "conv-a" }] });
    expect(checks[0]).toMatchObject({ conversation_ids: ["conv-a"], conversation_id: null });
  });

  it("keep how often and what the grader reads through a save and a load", () => {
    const rule = check({ level: "conversation", conversation_ids: ["conv-a", "m1"], when: "every_turn", kind: "reply_meets",
      rubric: "Quote prices", context: "run_value", context_path: "outputs.price" });
    const { checks } = parseChecks(serializeChecks([rule], "p"));
    expect(checks[0]).toMatchObject({ level: "conversation", conversation_ids: ["conv-a", "m1"], when: "every_turn",
      context: "run_value", context_path: "outputs.price" });
    expect(serializeCheck(checks[0])).toEqual(serializeCheck(rule));
    // At some point the rule reads only the reply, so neither the source nor its path is kept.
    const once = serializeCheck({ ...rule, when: "anywhere" });
    expect(once).not.toHaveProperty("context");
    expect(once).not.toHaveProperty("context_path");
  });

  it("can hold on every turn and read so", () => {
    expect(checkSentence(check({ level: "conversation", conversation_ids: ["conv-a"], when: "every_turn" }))).toBe(
      'On every turn, the reply should mention "London".',
    );
    expect(
      checkSentence(check({ level: "conversation", conversation_ids: ["conv-a"], kind: "only_tools", tools: [] })),
    ).toBe("No tool should be used.");
  });

  it("flag the ones the dataset lost", () => {
    const some = check({ level: "conversation", conversation_ids: ["conv-a", "gone"] });
    const all = check({ level: "conversation", conversation_ids: ["gone", "lost"] });
    expect(checkProblem(some, conversations)).toBeNull();
    expect(goneNote(some, conversations)).toBe("1 of its 2 conversations is no longer in the dataset, so it checks the one left.");
    expect(goneNote(check({ level: "conversation", conversation_ids: ["conv-a", "m1", "gone"] }), conversations)).toBe(
      "1 of its 3 conversations is no longer in the dataset, so it checks the other 2.",
    );
    expect(checkProblem(all, conversations)).toBe(
      "These conversations are no longer in the dataset. It will not be graded until you fix it.",
    );
    expect(goneNote(all, conversations)).toBeNull();
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
    expect(parseChecks(undefined)).toEqual({ checks: [], providerId: "", olderMethods: null });
  });
});

describe("checks that replace the older methods", () => {
  it("read as sentences", () => {
    expect(checkSentence(check({ kind: "reply_matches", match: "exact", when: "every_turn" }))).toBe(
      "On every turn, the reply should be exactly the expected reply.",
    );
    expect(checkSentence(check({ kind: "reply_matches", match: "meaning", level: "turn", case_id: "a2" }))).toBe(
      "The reply should say the same as the expected reply.",
    );
    expect(checkSentence(check({ kind: "reply_grounded", level: "conversation", conversation_id: "conv-a" }))).toBe(
      "On every turn, the reply should stick to the knowledge base.",
    );
    expect(checkSentence(check({ kind: "step_fails", expect: "should_not" }))).toBe(
      "In every conversation, no step should ever fail.",
    );
    expect(checkSentence(check({ kind: "step_fails", expect: "should_not", level: "turn", case_id: "a2" }))).toBe(
      "No step should fail.",
    );
    expect(checkSentence(check({ kind: "step_fails" }))).toBe("In every conversation, at some point, a step should fail.");
    expect(checkSentence(check({ kind: "reply_matches", match: "contains", expect: "should_not", when: "every_turn" }))).toBe(
      "On every turn, the reply should not contain the expected reply.",
    );
    expect(
      checkSentence(check({ kind: "reply_meets", rubric: "Quote prices", context: "knowledge_base", when: "every_turn" })),
    ).toBe('On every turn, the reply should do this: "Quote prices", graded with the knowledge-base passages.');
  });

  it("say Should or Should not, and those against each turn's own reply are checked on each turn", () => {
    expect(serializeCheck(check({ kind: "step_fails", expect: "should_not", text: "left over" }))).toEqual({
      id: "c1", expect: "should_not", kind: "step_fails", level: "every_conversation", when: "anywhere",
    });
    const { checks } = parseChecks({ checks: [{ id: "a", kind: "reply_matches", match: "exact", expect: "should_not" }] });
    expect(checks[0]).toMatchObject({ expect: "should_not", when: "every_turn", match: "exact" });
  });

  it("keep what the grader also reads only for a rule graded on each turn", () => {
    const rule = { kind: "reply_meets" as const, rubric: "R", context: "expected_reply" as const };
    expect(serializeCheck(check({ ...rule, when: "every_turn" }))).toMatchObject({ context: "expected_reply" });
    expect(serializeCheck(check(rule))).not.toHaveProperty("context");
  });

  it("need how closely the reply should match", () => {
    expect(checkMissing(check({ kind: "reply_matches" }))).toBe("Pick how closely it should match.");
    expect(checkMissing(check({ kind: "reply_matches", match: "contains" }))).toBeNull();
    expect(checkMissing(check({ kind: "reply_grounded" }))).toBeNull();
  });

  it("use the AI grader for same meaning, the knowledge base and rules", () => {
    expect(isAiGraded(check({ kind: "reply_matches", match: "meaning" }))).toBe(true);
    expect(isAiGraded(check({ kind: "reply_matches", match: "contains" }))).toBe(false);
    expect(isAiGraded(check({ kind: "step_fails" }))).toBe(false);
    expect(serializeChecks([check({ kind: "reply_grounded" })], "p1")).toMatchObject({ llm_provider_id: "p1" });
  });
});

describe("sticking to the facts as NLI and Provenance graded it", () => {
  const nli = check({
    kind: "reply_grounded", context: "expected_reply", grader: "nli", nli_model: "cross-encoder/nli-roberta-base",
    fail_on_contradiction: true, pass_score: 0.3, rubric: "left over", llm_provider_id: "p1",
  });
  const similar = check({
    kind: "reply_grounded", grader: "similarity", pass_score: 0.85, embedding: { type: "openai", model_name: " text-embedding-3-small ", model_id: "" },
  });

  it("read as the backend writes them", () => {
    expect(checkSentence(nli)).toBe(
      "On every turn, the reply should stick to the expected reply, graded by the NLI model, failing any contradiction (passes at 0.3).",
    );
    expect(checkSentence(similar)).toBe("On every turn, the reply should stick to the knowledge base, graded by text similarity (passes at 0.85).");
  });

  it("keep only their own grader's settings", () => {
    expect(serializeCheck(nli)).toEqual({
      id: "c1", expect: "should", kind: "reply_grounded", level: "every_conversation", when: "every_turn",
      context: "expected_reply", pass_score: 0.3, grader: "nli", nli_model: "cross-encoder/nli-roberta-base", fail_on_contradiction: true,
    });
    expect(serializeCheck(similar)).toMatchObject({ grader: "similarity", embedding: { type: "openai", model_name: "text-embedding-3-small" } });
    expect(serializeCheck({ ...similar, grader: null })).not.toHaveProperty("embedding");
  });

  it("need no AI grader", () => {
    expect(isAiGraded(nli)).toBe(false);
    expect(serializeChecks([nli, similar], "p1")).not.toHaveProperty("llm_provider_id");
  });
});

describe("older methods", () => {
  it("need converting while any of them runs", () => {
    expect(needsConversion([])).toBe(true);
    expect(needsConversion(["checks"])).toBe(false);
    expect(needsConversion(["checks", "contains"])).toBe(true);
  });

  it("keep their record through a save, and say what was left out until the editor saves", () => {
    const older = { techniques: ["contains"], left_out: ['Tool Usage: only "x" may be used.'] };
    expect(parseChecks(serializeChecks([check()], "", older)).olderMethods).toEqual(older);
    expect(leftOutNote(older)).toEqual(older.left_out);
    expect(leftOutNote({ ...older, reviewed: true })).toEqual([]);
    expect(leftOutNote(null)).toEqual([]);
  });
});

describe("every older-method setting as a check", () => {
  // The same sentences the backend writes; test_scenario_check_kinds.py holds them too.
  it.each<[Partial<ScenarioCheck>, string]>([
    [{ kind: "reply_mentions", text: "Hi", match: "exact", when: "every_turn" }, 'On every turn, the reply should be exactly "Hi".'],
    [{ kind: "route_taken", branch: "a", branch_label: "Refund", when: "every_turn" }, 'On every turn, a router should take "Refund".'],
    [
      { kind: "step_runs", step_type: "zendeskTicketNode", step_name: "Zendesk ticket" },
      'In every conversation, at some point, a step of type "Zendesk ticket" should run.',
    ],
    [
      { kind: "only_tools", tools: [{ tool_name: "a" }, { tool_name: "b" }], max_calls: 3, level: "conversation", conversation_id: "conv-a" },
      'Only the tools "a" and "b" should be used, called at most 3 times.',
    ],
    [{ kind: "only_tools", tools: [] }, "In every conversation, no tool should be used."],
    [
      { kind: "tool_called", tool: "t1", tool_name: "save_region", tools: [{ tool: "t2", tool_name: "change_mode" }], when: "every_turn" },
      'On every turn, one of the tools "save_region" or "change_mode" should be called.',
    ],
    [
      { kind: "tool_called", tool: "t1", tool_name: "save_region", max_calls: 2, succeeds: true, result_contains: "saved", when: "every_turn" },
      'On every turn, the tool "save_region" should be called at most 2 times and succeed and return a result that contains "saved".',
    ],
    [{ kind: "value_equals", path: "outputs.status", value: "ok", when: "every_turn" }, 'On every turn, the value at "outputs.status" should be "ok".'],
    [{ kind: "value_equals", path: "outputs.status", when: "every_turn" }, 'On every turn, the value at "outputs.status" should be the expected reply.'],
    [
      { kind: "reply_grounded", context: "tool_calls", rubric: "Numbers must match", pass_score: 0.9 },
      'On every turn, the reply should stick to the tool results, also: "Numbers must match" (passes at 0.9).',
    ],
    [
      { kind: "reply_meets", rubric: "Uses the step", context: "run_value", context_path: "trace.nodes.step.output", when: "every_turn" },
      'On every turn, the reply should do this: "Uses the step", graded with the value at "trace.nodes.step.output".',
    ],
    [{ kind: "reply_matches", match: "meaning", pass_score: 0.8 }, "On every turn, the reply should say the same as the expected reply (passes at 0.8)."],
  ])("reads %o as one sentence", (fields, sentence) => {
    expect(checkSentence(check({ text: undefined, ...fields }))).toBe(sentence);
  });

  it("keeps a tool's extra settings only for what should happen", () => {
    const tool = { kind: "tool_called" as const, tool: "t1", tool_name: "save_region", succeeds: true, min_calls: 2,
      tools: [{ tool: "t2", tool_name: "change_mode" }], result_not_empty: true };
    expect(serializeCheck(check({ ...tool, when: "every_turn" }))).toMatchObject({
      succeeds: true, min_calls: 2, result_not_empty: true, tools: [{ tool: "t2", tool_name: "change_mode" }],
    });
    const never = serializeCheck(check({ ...tool, expect: "should_not" }));
    for (const field of ["succeeds", "min_calls", "result_not_empty", "tools"]) expect(never).not.toHaveProperty(field);
    expect(checkSentence(check({ ...tool, expect: "should_not" }))).toBe(
      'In every conversation, the tool "save_region" should never be called.',
    );
  });

  it("keeps each tool's own values and result, for what should happen", () => {
    const several = check({
      kind: "tool_called",
      tool: "t1",
      tool_name: "save_region",
      args: { region: "uk" },
      tools: [{ tool: "t2", tool_name: "change_mode", args: { mode: " refund " }, result_contains: "saved", rows: [["mode", "refund"]] }],
    });
    // The same sentence the backend stores with each result.
    expect(checkSentence(several)).toBe(
      'In every conversation, at some point, one of the tools "save_region" (with region = uk) or "change_mode"' +
        ' (with mode = refund, returning a result that contains "saved") should be called.',
    );
    expect(checkSentence({ ...several, min_calls: 3, succeeds: true })).toBe(
      'In every conversation, at some point, one of the tools "save_region" (with region = uk) or "change_mode"' +
        ' (with mode = refund, returning a result that contains "saved") should be called at least 3 times in all and succeed.',
    );
    const saved = serializeCheck(several);
    expect(saved.args).toEqual({ region: "uk" });
    // The rows are the form's own; only the values are saved.
    expect(saved.tools).toEqual([{ tool: "t2", tool_name: "change_mode", args: { mode: "refund" }, result_contains: "saved" }]);
    const { checks } = parseChecks({ checks: [saved] });
    expect(checks[0].tools).toEqual([
      { tool: "t2", tool_name: "change_mode", args: { mode: "refund" }, result_contains: "saved" },
    ]);
    expect(serializeCheck(checks[0])).toEqual(saved);
    // A Should not reads only its own tool; allowed tools are names only.
    expect(serializeCheck({ ...several, expect: "should_not" })).not.toHaveProperty("tools");
    expect(serializeCheck(check({ kind: "only_tools", tools: [{ tool: "t2", args: { a: "b" } }] })).tools).toEqual([
      { tool: "t2" },
    ]);
  });

  it("saves each tool once", () => {
    const repeated = check({ kind: "tool_called", tool: "t1", tool_name: "save_region",
      tools: [{ tool: "t1", tool_name: "save_region" }, { tool: "t2", tool_name: "change_mode" }, { tool: "t2" }] });
    expect(serializeCheck(repeated).tools).toEqual([{ tool: "t2", tool_name: "change_mode" }]);
    const allowed = check({ kind: "only_tools", tools: [{ tool_name: "a" }, { tool_name: "a" }, { tool_name: "b" }] });
    expect(serializeCheck(allowed).tools).toEqual([{ tool_name: "a" }, { tool_name: "b" }]);
  });

  it("saves allowed tools with an empty list, and as Should not without counts", () => {
    expect(serializeCheck(check({ kind: "only_tools", tools: [] }))).toEqual({
      id: "c1", expect: "should", kind: "only_tools", level: "every_conversation", when: "anywhere", tools: [],
    });
    const never = check({ kind: "only_tools", expect: "should_not", tools: [{ tool_name: "a" }], max_calls: 2, succeeds: true });
    expect(serializeCheck(never)).toEqual({
      id: "c1", expect: "should_not", kind: "only_tools", level: "every_conversation", when: "anywhere", tools: [{ tool_name: "a" }],
    });
  });

  it("says which tools should not be used", () => {
    const two = check({ kind: "only_tools", expect: "should_not", tools: [{ tool_name: "a" }, { tool_name: "b" }] });
    expect(checkSentence(two)).toBe('In every conversation, none of the tools "a" and "b" should ever be used.');
    expect(checkSentence(check({ kind: "only_tools", expect: "should_not", tools: [{ tool_name: "a" }], level: "turn", case_id: "a2" }))).toBe(
      'The tool "a" should not be used.',
    );
    expect(checkMissing(check({ kind: "only_tools", expect: "should_not", tools: [] }))).toBe("Pick the tools it should not use.");
  });

  it("keeps a pass score only for a check graded by AI, and a path only for a value in the run", () => {
    expect(serializeCheck(check({ kind: "reply_meets", rubric: "R", pass_score: 0.7, when: "every_turn" }))).toMatchObject({ pass_score: 0.7 });
    expect(serializeCheck(check({ kind: "reply_matches", match: "exact", pass_score: 0.7 }))).not.toHaveProperty("pass_score");
    expect(serializeCheck(check({ kind: "reply_grounded", context: "knowledge_base", context_path: "x" }))).not.toHaveProperty("context_path");
    expect(serializeCheck(check({ kind: "reply_matches", match: "contains", rubric: "left over" }))).not.toHaveProperty("rubric");
  });

  it("round-trips the new settings", () => {
    const saved = serializeChecks([
      check({ kind: "only_tools", tools: [{ tool: "t1", tool_name: "save_region" }], agent: "a1", agent_name: "Agent", max_calls: 4 }),
      check({ id: "c2", kind: "step_runs", step_type: "zendeskTicketNode", step_name: "Zendesk ticket" }),
    ]);
    const { checks } = parseChecks(saved);
    expect(checks[0]).toMatchObject({ kind: "only_tools", tools: [{ tool: "t1", tool_name: "save_region" }], max_calls: 4, when: "anywhere" });
    expect(checks[1]).toMatchObject({ kind: "step_runs", step_type: "zendeskTicketNode" });
  });

  it("says what is missing", () => {
    expect(checkMissing(check({ kind: "only_tools", tools: [{}] }))).toBe("Pick each tool.");
    expect(checkMissing(check({ kind: "tool_called", tool: "t1", min_calls: 3, max_calls: 1 }))).toBe(
      "The fewest calls cannot be more than the most.",
    );
    expect(checkMissing(check({ kind: "value_equals" }))).toBe("Enter where the value is.");
    expect(checkMissing(check({ kind: "reply_grounded", context: "run_value" }))).toBe("Enter where the value is.");
    expect(checkMissing(check({ kind: "route_taken", branch: "a" }))).toBeNull();
    expect(checkMissing(check({ kind: "step_runs", step_type: "logNode" }))).toBeNull();
  });

  it("flags tools, step types and routers the workflow no longer has", () => {
    expect(checkProblem(check({ kind: "tool_called", tool: "tool-1", tools: [{ tool: "gone", tool_name: "gone" }] }), conversations, CATALOG)).toBe(
      'The tool "gone" is not in this workflow, so it can never be called.',
    );
    expect(checkProblem(check({ kind: "step_runs", step_type: "smsNode", step_name: "Sms" }), conversations, CATALOG)).toBe(
      'No step of type "Sms" is in this workflow, so none can run.',
    );
    expect(checkProblem(check({ kind: "route_taken", branch: "a" }), conversations, CATALOG)).toBeNull();
  });

  it("names a step type in words, as the backend does", () => {
    expect(stepTypeLabel("zendeskTicketNode")).toBe("Zendesk ticket");
    expect(stepTypeLabel("logNode")).toBe("Log");
  });
});

describe("settings a check no longer uses", () => {
  it("do not hold up saving", () => {
    const hidden = check({ kind: "reply_meets", rubric: "R", expect: "should_not", context: "run_value", context_path: "" });
    expect(checkMissing(hidden)).toBeNull();
    const shown = check({ kind: "reply_meets", rubric: "R", when: "every_turn", context: "run_value", context_path: "" });
    expect(checkMissing(shown)).toBe("Enter where the value is.");
    expect(checkMissing(check({ kind: "reply_matches", match: "exact", pass_score: 7 }))).toBeNull();
  });

  it("are not read out in the sentence", () => {
    expect(checkSentence(check({ kind: "reply_matches", match: "exact", pass_score: 0.8 }))).toBe(
      "On every turn, the reply should be exactly the expected reply.",
    );
    expect(checkSentence(check({ kind: "reply_meets", rubric: "R", when: "every_turn", pass_score: 0.1234567 }))).toBe(
      'On every turn, the reply should do this: "R" (passes at 0.123457).',
    );
  });
});

describe("counts and values", () => {
  it("take whole numbers, and a call that should happen cannot be capped at 0", () => {
    expect(checkMissing(check({ kind: "tool_called", tool: "t1", min_calls: 1.5 }))).toBe("Counts are whole numbers from 0.");
    expect(checkMissing(check({ kind: "tool_called", tool: "t1", max_calls: 0 }))).toBe(
      "At most 0 calls can never pass. Use Should not instead.",
    );
    expect(checkMissing(check({ kind: "only_tools", tools: [], max_calls: 0 }))).toBeNull();
  });

  it("read back values that are not text as their JSON", () => {
    const { checks } = parseChecks({ checks: [{ id: "a", kind: "tool_called", tool: "t1", args: { filters: { region: "uk" } } }] });
    expect(checks[0].args).toEqual({ filters: '{"region":"uk"}' });
  });

  it("let only these tools hold on every turn and count successful calls", () => {
    const item = check({ kind: "only_tools", tools: [{ tool_name: "a" }], when: "every_turn", max_calls: 1, succeeds: true });
    expect(checkSentence(item)).toBe('On every turn, only the tool "a" should be used, called successfully at most 1 time.');
    expect(serializeCheck(item)).toMatchObject({ when: "every_turn", succeeds: true, max_calls: 1 });
  });
});

describe("as the older methods graded", () => {
  it("a reply can stick to the expected reply, as NLI checked", () => {
    const item = check({ kind: "reply_grounded", context: "expected_reply" });
    expect(checkSentence(item)).toBe("On every turn, the reply should stick to the expected reply.");
    expect(serializeCheck(item)).toMatchObject({ context: "expected_reply" });
  });

  it("a check graded by AI keeps its own grader", () => {
    expect(serializeCheck(check({ kind: "reply_meets", rubric: "R", when: "every_turn", llm_provider_id: "p2" }))).toMatchObject({
      llm_provider_id: "p2",
    });
    expect(serializeCheck(check({ kind: "reply_mentions", text: "x", llm_provider_id: "p2" }))).not.toHaveProperty("llm_provider_id");
  });
});
