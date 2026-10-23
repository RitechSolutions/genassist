import { describe, expect, it } from "vitest";
import type {
  RunConversationResult,
  RunConversations,
  RunTurnResult,
  TestRun,
  Verdict,
} from "@/interfaces/testSuite.interface";
import type { TestToolRuleResult } from "@/interfaces/testEvaluation.interface";
import {
  compareGroup,
  compareRuns,
  comparisonOrder,
  conversationFindings,
  conversationsVerdictText,
  failedOnTurn,
  conversationChecksOnTurn,
  replyVerdict,
  turnCheckRows,
  turnCheckDetail,
  pairTurnChecks,
  pairChange,
  pairReplyChecks,
  changedTurnsByCheck,
  inTimeOrder,
  notComparedReason,
  pairChecks,
  checkDetail,
  hiddenCheckMoves,
  pairTurns,
  tallyItems,
  tallySlots,
  runCheckCount,
  tallyText,
  notEvaluatedReason,
  reviewOrder,
  rowItem,
  runConversationCounts,
  runConversationLabels,
  turnChecks,
  turnQuestions,
} from "@/views/TestSuites/helpers/runConversations";

const rule = (overrides: Partial<TestToolRuleResult> & { details?: Record<string, unknown> }): TestToolRuleResult => ({
  id: "r1",
  run_id: "run",
  technique: "checks",
  rule_id: "c1",
  scope: "turn",
  status: "passed",
  created_at: "",
  ...overrides,
});

const turn = (overrides: Partial<RunTurnResult> = {}): RunTurnResult => ({
  case_id: "t1",
  number: 1,
  message: "Hi",
  verdict: "passed",
  status: "scored",
  metrics: {},
  rules: [],
  has_trace: true,
  in_dataset: true,
  ...overrides,
});

const conversation = (
  key: string,
  verdict: Verdict,
  overrides: Partial<RunConversationResult> = {},
): RunConversationResult => ({
  key,
  verdict,
  turns: [turn()],
  rules: [],
  ...overrides,
});

const runOf = (conversations: RunConversationResult[]): RunConversations => ({
  run_id: "run",
  counts: { total: conversations.length, passed: 0, failed: 0, not_evaluated: 0 },
  conversations,
  other_rules: [],
});

describe("a run's verdict by conversation", () => {
  const run = (summary_metrics: Record<string, unknown>): TestRun => ({
    suite_id: "s",
    workflow_id: "w",
    status: "completed",
    techniques: ["contains"],
    summary_metrics,
  });

  it("is read from the run, or from its checks for runs that only counted those", () => {
    const counts = { total: 5, passed: 3, failed: 1, not_evaluated: 1 };
    expect(runConversationCounts(run({ _conversations: counts }))).toEqual(counts);
    expect(runConversationCounts({ ...run({ checks: { conversations: counts } }), techniques: ["checks"] })).toEqual(
      counts,
    );
    expect(runConversationCounts(run({ contains: { accuracy: 1 } }))).toBeNull();
  });

  it("reads a run's checks only when checks are all it graded", () => {
    const counts = { total: 5, passed: 5, failed: 0, not_evaluated: 0 };
    const mixed: TestRun = { ...run({ checks: { conversations: counts } }), techniques: ["checks", "contains"] };
    const checksOnly: TestRun = { ...run({ checks: { conversations: counts } }), techniques: ["checks"] };
    expect(runConversationCounts(mixed)).toBeNull();
    expect(runConversationCounts(checksOnly)).toEqual(counts);
  });

  it("keeps not evaluated apart from passed and failed", () => {
    expect(conversationsVerdictText({ total: 5, passed: 3, failed: 1, not_evaluated: 1 })).toBe(
      "3 of 5 conversations passed · 1 failed · 1 not evaluated",
    );
    expect(conversationsVerdictText({ total: 1, passed: 1, failed: 0, not_evaluated: 0 })).toBe(
      "1 of 1 conversation passed",
    );
    expect(conversationsVerdictText({ total: 2, passed: 0, failed: 0, not_evaluated: 2 })).toBe(
      "Nothing could be evaluated in 2 conversations",
    );
  });

  it("lists what needs attention first", () => {
    const ordered = reviewOrder([
      conversation("a", "passed"),
      conversation("b", "failed"),
      conversation("c", "not_evaluated"),
      conversation("d", "failed"),
    ]);
    expect(ordered.map((entry) => entry.key)).toEqual(["b", "d", "c", "a"]);
  });

  it("names conversations by their opening message", () => {
    const labels = runConversationLabels([
      conversation("conv-000001", "passed", { turns: [turn({ message: "Where is my order?" })] }),
      conversation("conv-000002", "passed", { turns: [turn({ message: "Hi" })] }),
      conversation("conv-000003", "passed", { turns: [turn({ message: "Hi" })] }),
      conversation("conv-000004", "passed", { turns: [turn({ message: "" })] }),
    ]);
    expect([...labels.values()]).toEqual(["Where is my order?", "Hi #000002", "Hi #000003", "Conversation #000004"]);
  });
});

describe("what a whole-conversation check says under its sentence", () => {
  const check = (status: Verdict, details: Record<string, unknown>) =>
    rowItem(rule({ status, scope: "conversation", details: { expected: "The check", ...details } }));
  const none = { lead: null, turns: [], facts: [] };

  it("says it held on every turn, or that no turn had it", () => {
    expect(
      checkDetail(
        check("passed", { when: "every_turn", expect: "should_not", observed: "Not on any of its 8 turns." }),
      ),
    ).toEqual({ ...none, text: "Holds on every turn." });
    expect(
      checkDetail(
        check("failed", { when: "anywhere", expect: "should", observed: "Not on any of its 8 turns. Turn 8: ..." }),
      ),
    ).toEqual({ ...none, text: "No turn has this." });
  });

  it("names the turns where it held or broke", () => {
    const broke = check("failed", {
      when: "every_turn",
      expect: "should",
      turns: [2, 6, 8],
      facts: ["a", "b", "c"],
      observed: "Turn 2: a",
    });
    expect(checkDetail(broke)).toEqual({
      text: null,
      lead: "Doesn't hold here",
      turns: [2, 6, 8],
      facts: ["a", "b", "c"],
      rest: null,
    });
    const held = check("passed", { when: "anywhere", expect: "should", turns: [4], facts: ["mode was refund"] });
    expect(checkDetail(held)).toMatchObject({ lead: "Holds here", turns: [4] });
  });

  it("keeps a grader's reason, a count, and why it was not evaluated", () => {
    expect(checkDetail(check("passed", { when: "every_turn", score: 0.9, observed: "It was polite." })).text).toBe(
      "It was polite.",
    );
    const counted = check("failed", { turns: [1, 3], observed: "Called 3 times.", rule: { max_calls: 2 } });
    expect(checkDetail(counted)).toMatchObject({ text: "Called 3 times.", lead: "On these turns", turns: [1, 3] });
    expect(checkDetail(check("not_evaluated", { comment: "The AI grader could not be reached." })).text).toBe(
      "The AI grader could not be reached.",
    );
  });
});

describe("how many checks a run graded", () => {
  const rule = (rule_id: string, technique = "checks") => ({ rule_id, technique }) as unknown as TestToolRuleResult;

  it("counts each check once, wherever it was graded, and leaves out older methods", () => {
    const data = {
      run_id: "run",
      counts: { total: 2, passed: 1, failed: 1, not_evaluated: 0 },
      conversations: [
        { key: "a", verdict: "passed", rules: [rule("every")], turns: [{ rules: [rule("turn")] }] },
        { key: "b", verdict: "failed", rules: [rule("every"), rule("tool", "tool_used")], turns: [] },
      ],
      other_rules: [rule("lost")],
    } as unknown as RunConversations;
    expect(runCheckCount(data)).toBe(3);
  });
});

describe("lining up a column of tallies", () => {
  const counts = (not_evaluated = 0) => ({ passed: 1, failed: 0, not_evaluated, total: 1 + not_evaluated });

  it("keeps a slot for passed and failed even when nothing failed", () => {
    expect(tallySlots([counts(), null])).toEqual(["passed", "failed"]);
  });

  it("adds not evaluated only when a run in the column has it", () => {
    expect(tallySlots([counts(), counts(2)])).toEqual(["passed", "failed", "not_evaluated"]);
  });
});

describe("a turn's results", () => {
  it("read checks as their sentence and what was seen", () => {
    const failed = rule({
      status: "failed",
      details: { expected: 'The tool "save_region" should not be called', observed: "Called once" },
    });
    const skipped = rule({
      id: "r2",
      status: "not_evaluated",
      details: { expected: "The reply should mention RingGo", observed: "not evaluated", comment: "No reply." },
    });
    expect(
      turnChecks(turn({ rules: [failed, skipped] })).map(({ key, status, title, actual, note }) => ({
        key,
        status,
        title,
        actual,
        note,
      })),
    ).toEqual([
      {
        key: "r1",
        status: "failed",
        title: 'The tool "save_region" should not be called',
        actual: "Called once",
        note: null,
      },
      { key: "r2", status: "not_evaluated", title: "The reply should mention RingGo", actual: null, note: "No reply." },
    ]);
  });

  it("group the older methods under plain questions, keeping their names", () => {
    const questions = turnQuestions(
      turn({
        metrics: {
          contains: { score: false, passed: false, comment: "Expected text not found in output." },
          nli_eval: { score: null, passed: false, not_evaluated: true, comment: "No sources were used." },
          llm_judge: {
            score: 1,
            passed: true,
            details: [{ passed: true, comment: "ok", rule_number: 1, label: "Polite", reason: "It was." } as never],
          },
        },
        rules: [
          rule({
            technique: "route_taken",
            details: { rule_summary: "Takes the refund branch", expected: "refund", observed: "refund" },
          }),
        ],
      }),
    );
    expect(questions.map((question) => [question.label, question.status])).toEqual([
      ["Is the answer correct?", "failed"],
      ["Did it use the right tools and route?", "passed"],
      ["Is it grounded in the evidence?", "not_evaluated"],
    ]);
    const [answer, path] = questions;
    expect(answer.items.map((item) => [item.method, item.note])).toEqual([
      ["Contains", "Expected text not found in output."],
      ["LLM Judge", null],
    ]);
    // One rubric reads as the method itself.
    expect(answer.items[1]).toMatchObject({ title: "LLM Judge", expected: "Polite", actual: "It was." });
    expect(answer.items[1].items).toBeUndefined();
    expect(path.items[0]).toMatchObject({ title: "Takes the refund branch", expected: "refund", actual: "refund" });
  });

  it("read judge rubrics that could not be graded as not evaluated, and one rubric as the method", () => {
    const rubrics = (details: Record<string, unknown>[]) =>
      turnQuestions(turn({ metrics: { llm_judge: { score: 1, passed: true, details: details as never } } }))[0]
        .items[0];
    const several = rubrics([
      { label: "Polite", passed: true, reason: "It was." },
      { label: "Grounded", passed: false, not_evaluated: true, comment: "No sources were retrieved." },
      { label: "Short", passed: false, error: true, comment: "The grader failed." },
    ]);
    expect(several.items?.map((item) => [item.title, item.status, item.note ?? null])).toEqual([
      ["Polite", "passed", null],
      ["Grounded", "not_evaluated", "No sources were retrieved."],
      ["Short", "not_evaluated", "The grader failed."],
    ]);
    const one = rubrics([{ label: "Polite", passed: true, reason: "It was." }]);
    expect(one.items).toBeUndefined();
    expect([one.expected, one.actual]).toEqual(["Polite", "It was."]);
  });

  it("place a whole-conversation check's turns", () => {
    const item = rowItem(
      rule({ scope: "conversation", status: "failed", details: { expected: "x", observed: "Turn 2: y", turns: [2] } }),
    );
    expect(item.turns).toEqual([2]);
  });

  it("show a whole-conversation check on each turn it failed, with what that turn did", () => {
    const missed = rule({
      scope: "every_conversation",
      status: "failed",
      details: {
        expected: "On every turn, no step should fail.",
        turns: [2, 3],
        facts: ["1 error: a.", "1 error: b."],
      },
    });
    const whole = conversation("a", "failed", { rules: [missed] });
    expect(failedOnTurn(whole, 3)).toEqual([
      expect.objectContaining({
        title: "On every turn, no step should fail.",
        actual: "1 error: b.",
        status: "failed",
      }),
    ]);
    expect(failedOnTurn(whole, 1)).toEqual([]);
    const older = conversation("a", "failed", {
      rules: [rule({ status: "failed", details: { expected: "x", turns: [2] } })],
    });
    expect(failedOnTurn(older, 2)[0].actual).toBeNull();
  });

  it("give every turn it read a result, but an at-some-point check that was met only where it was met", () => {
    const missed = rule({
      scope: "every_conversation",
      status: "failed",
      details: {
        expected: "On every turn, mention refund.",
        when: "every_turn",
        expect: "should",
        turns: [2],
        facts: ["No."],
        checked: [1, 2, 3],
      },
    });
    const met = rule({
      id: "r2",
      scope: "every_conversation",
      status: "passed",
      details: {
        expected: "At some point, take the hand-over.",
        when: "anywhere",
        expect: "should",
        turns: [3],
        facts: ["Took it."],
        checked: [1, 2, 3],
      },
    });
    const whole = conversation("a", "failed", { rules: [missed, met] });
    const on = (number: number) =>
      conversationChecksOnTurn(whole, number).map((item) => [item.title, item.status, item.whole]);
    expect(on(1)).toEqual([["On every turn, mention refund.", "passed", true]]);
    expect(on(2)).toEqual([["On every turn, mention refund.", "failed", true]]);
    expect(on(3)).toEqual([
      ["On every turn, mention refund.", "passed", true],
      ["At some point, take the hand-over.", "passed", true],
    ]);
    // A turn it did not read says nothing either way.
    expect(on(4)).toEqual([]);
  });

  it("fail every turn it read when an at-some-point check was never met, and read older runs' turns that ran", () => {
    const never = rule({
      scope: "every_conversation",
      status: "failed",
      details: {
        expected: "At some point, mention zebra.",
        when: "anywhere",
        expect: "should",
        observed: "Not on any of its 2 turns.",
      },
    });
    const whole = conversation("a", "failed", {
      rules: [never],
      turns: [turn({ case_id: "t1" }), turn({ case_id: "t2", number: 2 })],
    });
    expect(conversationChecksOnTurn(whole, 1).map((item) => item.status)).toEqual(["failed"]);
    expect(conversationChecksOnTurn(whole, 2).map((item) => item.status)).toEqual(["failed"]);
  });

  it("read a reply as failed when a whole-conversation check broke on it, even if its own checks passed", () => {
    const own = rule({ id: "own", status: "passed", details: { expected: "Mention refunds." } });
    const broke = rule({
      id: "w",
      scope: "every_conversation",
      status: "failed",
      details: {
        expected: "Never hand over.",
        when: "anywhere",
        expect: "should_not",
        turns: [1],
        facts: ["It did."],
        checked: [1, 2],
      },
    });
    const whole = conversation("a", "failed", {
      rules: [broke],
      turns: [
        turn({ case_id: "t1", verdict: "passed", rules: [own] }),
        turn({ case_id: "t2", number: 2, verdict: "not_evaluated" }),
      ],
    });
    expect(replyVerdict(whole.turns[0], whole)).toBe("failed");
    expect(replyVerdict(whole.turns[1], whole)).toBe("passed");
  });

  it("say a check as its page does, and what each turn it read did", () => {
    const never = rule({
      scope: "every_conversation",
      status: "failed",
      details: {
        expected: 'In every conversation, the reply should never mention "Amazon".',
        when: "anywhere",
        expect: "should_not",
        turns: [2],
        facts: ['The reply mentioned "Amazon".'],
        checked: [1, 2],
        checked_facts: ['The reply did not mention "Amazon".', 'The reply mentioned "Amazon".'],
        rule: {
          id: "c1",
          kind: "reply_mentions",
          text: "Amazon",
          when: "anywhere",
          level: "every_conversation",
          expect: "should_not",
        },
      },
    });
    const whole = conversation("a", "failed", {
      rules: [never],
      turns: [turn({ case_id: "t1" }), turn({ case_id: "t2", number: 2 })],
    });
    expect(rowItem(never).title).toBe('No reply should mention "Amazon".');
    expect(conversationChecksOnTurn(whole, 1).map((item) => [item.status, item.actual])).toEqual([
      ["passed", 'The reply did not mention "Amazon".'],
    ]);
    expect(conversationChecksOnTurn(whole, 2).map((item) => [item.status, item.actual])).toEqual([
      ["failed", 'The reply mentioned "Amazon".'],
    ]);
  });

  it("list each turn check with its turn, and pair them across runs", () => {
    const missed = rule({
      id: "m",
      status: "failed",
      details: { expected: "The reply should mention working days.", observed: "It did not." },
    });
    const held = rule({
      id: "h",
      status: "passed",
      details: { expected: "The reply should mention working days.", observed: "It did." },
    });
    const earlier = conversation("a", "passed", {
      turns: [turn({ case_id: "t1" }), turn({ case_id: "t5", number: 5, rules: [held] })],
    });
    const later = conversation("a", "failed", {
      turns: [turn({ case_id: "t1" }), turn({ case_id: "t5", number: 5, rules: [missed] })],
    });
    const [row] = turnCheckRows(later);
    expect(row.turn).toBe(5);
    expect(turnCheckDetail(row.item, row.turn)).toEqual({ text: null, lead: null, turns: [5], facts: ["It did not."] });
    const [paired] = pairTurnChecks(earlier, later);
    expect([paired.before?.item.status, paired.after?.item.status]).toEqual(["passed", "failed"]);
  });

  it("say what an older run's unnamed turns did, from the check", () => {
    const never = rule({
      scope: "every_conversation",
      status: "passed",
      details: {
        expected: "x",
        when: "anywhere",
        expect: "should_not",
        observed: "Not on any of its 2 turns.",
        rule: {
          id: "c1",
          kind: "reply_mentions",
          text: "Amazon",
          when: "anywhere",
          level: "every_conversation",
          expect: "should_not",
        },
      },
    });
    const whole = conversation("a", "passed", {
      rules: [never],
      turns: [turn({ case_id: "t1" }), turn({ case_id: "t2", number: 2 })],
    });
    expect(conversationChecksOnTurn(whole, 2)[0].actual).toBe('The reply did not mention "Amazon".');
  });

  it("leave a count or a grade of the whole conversation off its turns", () => {
    const counted = rule({
      scope: "every_conversation",
      status: "passed",
      details: { expected: "x", when: "anywhere", rule: { max_calls: 2 } },
    });
    const whole = conversation("a", "passed", { rules: [counted], turns: [turn({ case_id: "t1" })] });
    expect(conversationChecksOnTurn(whole, 1)).toEqual([]);
  });

  it("name the turns read when not every turn could be", () => {
    const partial = rowItem(
      rule({
        scope: "conversation",
        status: "passed",
        details: { expected: "x", when: "every_turn", expect: "should", checked: [1, 3] },
      }),
    );
    expect(checkDetail(partial, 4)).toEqual({
      text: null,
      lead: "Holds on every turn it could check",
      turns: [1, 3],
      facts: [],
      rest: "Turns 2, 4 could not be checked.",
    });
    expect(checkDetail(partial, 2).text).toBe("Holds on every turn.");
  });

  it("leave out turns with no expected reply, for a check against it", () => {
    const exact = rowItem(
      rule({
        scope: "every_conversation",
        status: "passed",
        details: {
          expected: "x",
          kind: "reply_matches",
          when: "every_turn",
          expect: "should",
          checked: [1],
          rule: { id: "c1", kind: "reply_matches", match: "exact", when: "every_turn", level: "every_conversation" },
        },
      }),
    );
    expect(checkDetail(exact, 3)).toMatchObject({ text: "Holds on every turn.", turns: [] });
  });
});

describe("a conversation's findings", () => {
  it("say what failed, turn by turn, then on the whole conversation", () => {
    const failedCheck = rule({
      status: "failed",
      details: { expected: 'The tool "save_region" should not be called' },
    });
    const lines = conversationFindings(
      conversation("a", "failed", {
        turns: [
          turn({ rules: [failedCheck] }),
          turn({ number: 2, status: "execution_failed", verdict: "failed", reason: "Execution failed: boom" }),
          turn({ number: 3, metrics: { contains: { score: false, passed: false } } }),
          turn({
            number: 4,
            rules: [
              rule({
                id: "t",
                technique: "tool_used",
                status: "failed",
                details: { rule_summary: 'Any agent must use "Save region" on turn 4.' },
              }),
            ],
          }),
        ],
        rules: [
          rule({
            id: "w",
            scope: "conversation",
            status: "failed",
            details: { expected: "The reply should never mention RingGo" },
          }),
        ],
      }),
    );
    expect(lines).toEqual([
      'Turn 1: The tool "save_region" should not be called',
      "Turn 2: the turn did not finish",
      "Turn 3: Is the answer correct?",
      'Turn 4: Any agent must use "Save region" on turn 4.',
      "The reply should never mention RingGo",
    ]);
  });

  it("say why nothing could be evaluated", () => {
    const skipped = conversation("a", "not_evaluated", {
      turns: [
        turn(),
        turn({
          number: 2,
          status: "skipped",
          verdict: "not_evaluated",
          reason: "This turn did not run because the conversation was waiting for a person.",
        }),
      ],
    });
    expect(notEvaluatedReason(skipped)).toBe(
      "Turn 2: This turn did not run because the conversation was waiting for a person.",
    );
    const timedOut = conversation("b", "not_evaluated", {
      rules: [
        rule({
          scope: "conversation",
          status: "not_evaluated",
          details: { comment: "The AI grader ran out of time for this run." },
        }),
      ],
    });
    expect(notEvaluatedReason(timedOut)).toBe("The AI grader ran out of time for this run.");
    expect(notEvaluatedReason(conversation("c", "not_evaluated"))).toBe("Nothing checks this conversation.");
    const noResult = conversation("d", "not_evaluated", {
      turns: [turn({ status: null, verdict: "not_evaluated", reason: "This turn has no result in this run." })],
    });
    expect(notEvaluatedReason(noResult)).toBe("Turn 1: This turn has no result in this run.");
  });

  it("names the check whose grading broke before any other reason", () => {
    const broke = conversation("e", "not_evaluated", {
      rules: [
        rule({
          id: "r1",
          scope: "conversation",
          status: "not_evaluated",
          details: { comment: "No turn of this conversation has an expected reply in the dataset." },
        }),
        rule({
          id: "r2",
          scope: "conversation",
          status: "not_evaluated",
          details: { comment: "Turn 2: The AI grader did not answer.", error: true },
        }),
      ],
    });
    expect(notEvaluatedReason(broke)).toBe("Turn 2: The AI grader did not answer.");
    const onTurn = conversation("f", "not_evaluated", {
      turns: [
        turn({
          rules: [
            rule({
              status: "not_evaluated",
              details: { comment: "The NLI model could not grade this reply.", error: true },
            }),
          ],
        }),
      ],
    });
    expect(notEvaluatedReason(onTurn)).toBe("Turn 1: The NLI model could not grade this reply.");
    expect(notEvaluatedReason(conversation("g", "not_evaluated"), "The checks could not be graded in this run.")).toBe(
      "The checks could not be graded in this run.",
    );
  });
});

describe("comparing two runs", () => {
  it("matches conversations and puts new failures before fixes", () => {
    const baseline = runOf([
      conversation("a", "passed"),
      conversation("b", "failed"),
      conversation("c", "failed"),
      conversation("d", "passed"),
      conversation("gone", "passed"),
    ]);
    const current = runOf([
      conversation("a", "failed"),
      conversation("b", "failed"),
      conversation("c", "passed"),
      conversation("d", "passed"),
      conversation("new", "not_evaluated"),
    ]);

    const comparison = compareRuns(baseline, current);

    expect(comparison.changes.map((change) => [change.key, change.change])).toEqual([
      ["a", "newly_failing"],
      ["b", "still_failing"],
      ["c", "fixed"],
      ["d", "unchanged"],
      ["new", "one_run_only"],
      ["gone", "one_run_only"],
    ]);
    expect(comparison.verdict).toBe("mixed");
  });

  it("tells coverage changes apart from fixes and failures", () => {
    const comparison = compareRuns(
      runOf([conversation("a", "not_evaluated"), conversation("b", "passed"), conversation("c", "failed")]),
      runOf([conversation("a", "passed"), conversation("b", "not_evaluated"), conversation("c", "not_evaluated")]),
    );
    expect(comparison.changes.map((change) => change.change)).toEqual([
      "newly_passing",
      "no_longer_evaluated",
      "no_longer_evaluated",
    ]);
    expect(comparison.changes.map(compareGroup)).toEqual(["newly_passing", "not_compared", "not_compared"]);
    // Newly passing on its card, and a pass lost to not being evaluated, so the verdict is Mixed.
    expect([comparison.verdict, comparison.noLongerEvaluated]).toEqual(["mixed", { passed: 1, failed: 1 }]);
  });

  it("gives the verdict the cards give when no conversation that passed lost its evaluation", () => {
    const one = (verdict: Verdict) => runOf([conversation("a", verdict)]);
    expect(compareRuns(one("not_evaluated"), one("failed")).verdict).toBe("worse");
    expect(compareRuns(one("not_evaluated"), one("passed")).verdict).toBe("better");
    expect(compareRuns(one("failed"), one("failed")).verdict).toBe("same");
  });

  it("does not say Same when a conversation that passed is no longer evaluated", () => {
    const one = (verdict: Verdict) => runOf([conversation("a", verdict)]);
    const lostPass = compareRuns(one("passed"), one("not_evaluated"));
    expect([lostPass.verdict, lostPass.noLongerEvaluated]).toEqual(["worse", { passed: 1, failed: 0 }]);
    // One that failed is neither better nor worse now, so it is only listed.
    const lostFail = compareRuns(one("failed"), one("not_evaluated"));
    expect([lostFail.verdict, lostFail.noLongerEvaluated]).toEqual(["same", { passed: 0, failed: 1 }]);
    const both = compareRuns(
      runOf([conversation("a", "passed"), conversation("b", "failed")]),
      runOf([conversation("a", "not_evaluated"), conversation("b", "passed")]),
    );
    expect(both.verdict).toBe("mixed");
  });

  it("lets the checks decide when no conversation changed result, and says Same only when nothing moved", () => {
    const whole = (id: string, status: Verdict) =>
      rule({
        id,
        rule_id: id,
        scope: "every_conversation",
        status,
        details: { expected: `Should ${id}`, observed: "x" },
      });
    const run = (...rules: TestToolRuleResult[]) => runOf([conversation("a", "failed", { rules })]);
    const fixed = compareRuns(
      run(whole("a", "failed"), whole("b", "failed")),
      run(whole("a", "passed"), whole("b", "failed")),
    );
    expect([fixed.verdict, fixed.fromChecks, fixed.checks]).toEqual(["better", true, { better: 1, worse: 0 }]);
    expect(fixed.changes[0].checks).toEqual({ better: 1, worse: 0 });
    expect(
      compareRuns(run(whole("a", "passed"), whole("b", "failed")), run(whole("a", "failed"), whole("b", "failed")))
        .verdict,
    ).toBe("worse");
    expect(
      compareRuns(run(whole("a", "passed"), whole("b", "failed")), run(whole("a", "failed"), whole("b", "passed")))
        .verdict,
    ).toBe("mixed");
    const still = compareRuns(run(whole("a", "failed")), run(whole("a", "failed")));
    expect([still.verdict, still.fromChecks]).toEqual(["same", false]);
  });

  it("shows a conversation's moved checks only when its result stayed the same", () => {
    const whole = (id: string, status: Verdict) =>
      rule({ id, rule_id: id, scope: "every_conversation", status, details: { expected: `Should ${id}`, observed: "x" } });
    const run = (verdict: Verdict, ...rules: TestToolRuleResult[]) => runOf([conversation("a", verdict, { rules })]);
    // Still failing with a check fixed: its result alone would hide that.
    const still = compareRuns(
      run("failed", whole("a", "failed"), whole("b", "failed")),
      run("failed", whole("a", "passed"), whole("b", "failed")),
    );
    expect(hiddenCheckMoves(still.changes[0])).toBe(true);
    // Newly passing: its result already says its checks were fixed.
    const fixed = compareRuns(run("failed", whole("a", "failed")), run("passed", whole("a", "passed")));
    expect(fixed.changes[0].checks).toEqual({ better: 1, worse: 0 });
    expect(hiddenCheckMoves(fixed.changes[0])).toBe(false);
    // The run's total is what the rows' pills add up to, so a changed result is not counted again.
    expect([still.checks, fixed.checks, fixed.verdict, fixed.fromChecks]).toEqual([
      { better: 1, worse: 0 },
      { better: 0, worse: 0 },
      "better",
      false,
    ]);
  });

  it("says Better, Worse or Same", () => {
    const one = (verdict: Verdict) => runOf([conversation("a", verdict)]);
    expect(compareRuns(one("failed"), one("passed")).verdict).toBe("better");
    expect(compareRuns(one("passed"), one("failed")).verdict).toBe("worse");
    expect(compareRuns(one("passed"), one("passed")).verdict).toBe("same");
  });

  it("counts each conversation under one of four changes, and the rest as not compared", () => {
    const comparison = compareRuns(
      runOf([
        conversation("a", "passed"),
        conversation("b", "failed"),
        conversation("c", "failed"),
        conversation("d", "passed"),
        conversation("e", "not_evaluated"),
        conversation("f", "passed"),
        conversation("g", "passed"),
      ]),
      runOf([
        conversation("a", "failed"),
        conversation("b", "failed"),
        conversation("c", "passed"),
        conversation("d", "passed"),
        conversation("e", "passed"),
        conversation("f", "not_evaluated"),
        conversation("h", "passed"),
      ]),
    );
    expect(Object.fromEntries(comparison.changes.map((change) => [change.key, compareGroup(change)]))).toEqual({
      a: "newly_failing",
      b: "still_failing",
      c: "newly_passing",
      d: "still_passing",
      e: "newly_passing",
      f: "not_compared",
      g: "not_compared",
      h: "not_compared",
    });
    expect(comparisonOrder(comparison).map((change) => change.key)).toEqual(["a", "b", "c", "e", "d", "f", "h", "g"]);
    const reason = (key: string) =>
      notComparedReason(comparison.changes.find((change) => change.key === key)!, "Run 2", "Run 5");
    expect(reason("f")).toBe("Not evaluated in Run 5.");
    expect(reason("g")).toBe("Only in Run 2.");
    expect(reason("h")).toBe("Only in Run 5.");
    const neither = compareRuns(
      runOf([conversation("x", "not_evaluated")]),
      runOf([conversation("x", "not_evaluated")]),
    );
    expect(compareGroup(neither.changes[0])).toBe("not_compared");
    expect(notComparedReason(neither.changes[0], "Run 2", "Run 5")).toBe("Not evaluated in either run.");
  });

  it("reads two runs forward in time, whichever was picked first", () => {
    const run = (id: string, day: number): TestRun => ({
      id,
      suite_id: "s",
      workflow_id: "w",
      status: "completed",
      techniques: [],
      created_at: `2026-10-0${day}T10:00:00Z`,
    });
    expect(inTimeOrder(run("late", 5), run("early", 2)).map((entry) => entry.id)).toEqual(["early", "late"]);
    expect(inTimeOrder(run("early", 2), run("late", 5)).map((entry) => entry.id)).toEqual(["early", "late"]);
  });

  it("matches a conversation's turns and checks across two runs", () => {
    const earlier = conversation("a", "passed", {
      turns: [turn({ case_id: "t1" }), turn({ case_id: "t2", number: 2 })],
      rules: [
        rule({ id: "x1", rule_id: "c1", scope: "conversation", details: { expected: "Should ask for the plate" } }),
        rule({ id: "x2", rule_id: "c2", scope: "conversation", details: { expected: "Should not share a number" } }),
      ],
    });
    const later = conversation("a", "failed", {
      turns: [turn({ case_id: "t1" }), turn({ case_id: "t3", number: 2 })],
      rules: [
        rule({
          id: "y1",
          rule_id: "c1",
          scope: "conversation",
          status: "failed",
          details: { expected: "Should ask for the plate", observed: "It never asked" },
        }),
      ],
    });
    expect(pairTurns(earlier, later).map(({ key, before, after }) => [key, Boolean(before), Boolean(after)])).toEqual([
      ["t1", true, true],
      ["t3", false, true],
      ["t2", true, false],
    ]);
    expect(
      pairChecks(earlier, later).map((row) => [
        row.key,
        row.title,
        row.before?.status,
        row.after?.status,
        row.after?.actual,
      ]),
    ).toEqual([
      ["checks:c1", "Should ask for the plate", "passed", "failed", "It never asked"],
      ["checks:c2", "Should not share a number", "passed", undefined, undefined],
    ]);
  });
});

describe("how a reply's checks went", () => {
  const item = (status: Verdict, key: string) => ({ key, status, title: key });

  it("says it in one line, failures first", () => {
    expect(tallyText(tallyItems([]))).toBeNull();
    expect(tallyText(tallyItems([item("passed", "a"), item("passed", "b"), item("passed", "c")]))).toBe(
      "3 checks passed",
    );
    expect(tallyText(tallyItems([item("passed", "a"), item("failed", "b"), item("passed", "c")]))).toBe(
      "1 of 3 checks failed",
    );
    expect(tallyText(tallyItems([item("failed", "a")]))).toBe("1 check failed");
    expect(tallyText(tallyItems([item("not_evaluated", "a"), item("not_evaluated", "b")]))).toBe("Not evaluated");
    expect(tallyText(tallyItems([item("passed", "a"), item("not_evaluated", "b")]))).toBe(
      "1 check passed · 1 not evaluated",
    );
  });

  it("counts each older method under its question", () => {
    const question = {
      key: "answer",
      label: "Is the answer correct?",
      status: "failed" as Verdict,
      items: [item("failed", "m1"), item("passed", "m2")],
    };
    expect(tallyItems([item("passed", "a")], [question])).toEqual({ passed: 2, failed: 1, notEvaluated: 0, total: 3 });
  });
});

describe("one reply's checks in two runs", () => {
  const check = (id: string, status: Verdict, expected: string) =>
    rule({ id, rule_id: id, status, details: { expected, observed: `${expected}: ${status}` } });

  it("pairs them by check, worse first, then better, then the rest", () => {
    const earlier = conversation("a", "passed", {
      turns: [
        turn({
          rules: [check("a", "passed", "Should A"), check("b", "failed", "Should B"), check("c", "passed", "Should C")],
        }),
      ],
    });
    const later = conversation("a", "failed", {
      turns: [
        turn({
          rules: [check("a", "passed", "Should A"), check("b", "passed", "Should B"), check("c", "failed", "Should C")],
        }),
      ],
    });
    const pairs = pairReplyChecks(
      { turn: earlier.turns[0], conversation: earlier },
      { turn: later.turns[0], conversation: later },
    );
    expect(pairs.map((pair) => [pair.title, pairChange(pair)])).toEqual([
      ["Should C", "worse"],
      ["Should B", "better"],
      ["Should A", null],
    ]);
  });

  it("names, for each check, only the turns where it went differently", () => {
    const earlier = conversation("a", "failed", {
      turns: [
        turn({ case_id: "t1", rules: [check("a", "passed", "Should A")] }),
        turn({ case_id: "t2", number: 2, rules: [check("b", "passed", "Should B")] }),
      ],
    });
    const later = conversation("a", "failed", {
      turns: [
        turn({ case_id: "t1", rules: [check("a", "passed", "Should A")] }),
        turn({ case_id: "t2", number: 2, rules: [check("b", "failed", "Should B")] }),
      ],
    });
    const changed = changedTurnsByCheck(earlier, later);
    expect([...changed.keys()]).toEqual(["turn:Should B"]);
    expect([...(changed.get("turn:Should B")?.after ?? [])]).toEqual([2]);
  });

  it("does not count a check on one side only as a change", () => {
    const only = conversation("a", "passed", { turns: [turn({ rules: [check("a", "passed", "Should A")] })] });
    const [pair] = pairReplyChecks({ turn: only.turns[0], conversation: only }, undefined);
    expect([pair.before?.status, pair.after, pairChange(pair)]).toEqual(["passed", undefined, null]);
  });
});
