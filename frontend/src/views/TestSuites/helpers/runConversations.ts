import type {
  ConversationCounts,
  RunConversationResult,
  RunConversations,
  RunTurnResult,
  TestResultMetric,
  TestRun,
  Verdict,
} from "@/interfaces/testSuite.interface";
import type { ScenarioCheck, TestToolRuleResult, ToolRuleResultDetails } from "@/interfaces/testEvaluation.interface";
import { checkSentence, conversationSentence, parseChecks, turnFact } from "./checks";
import { labelFromMessage } from "./datasetConversations";
import { methodLabel } from "./methodLabels";
import { toolActualText, toolExpectedText } from "./toolRuleText";

const plural = (count: number, noun: string): string => `${count} ${noun}${count === 1 ? "" : "s"}`;

/** A run's verdict by conversation, stored when it finished, or null for older runs. */
export const runConversationCounts = (run: TestRun | null | undefined): ConversationCounts | null => {
  const metrics = run?.summary_metrics as Record<string, unknown> | undefined;
  // Checks-only runs counted their conversations before every run did; a run with older
  // methods too cannot be read from its checks alone.
  const checksOnly = (run?.techniques ?? []).every((technique) => technique === "checks");
  const fallback = checksOnly ? (metrics?.checks as { conversations?: unknown } | undefined)?.conversations : undefined;
  const counts = (metrics?._conversations ?? fallback) as ConversationCounts | undefined;
  return counts && counts.total ? counts : null;
};

const checkResults = (data: RunConversations): TestToolRuleResult[] =>
  [
    ...data.conversations.flatMap((conversation) => [
      ...conversation.rules,
      ...conversation.turns.flatMap((turn) => turn.rules),
    ]),
    ...data.other_rules,
  ].filter((rule) => rule.technique === "checks");

/** How many checks a run graded, each counted once however many conversations it covered. */
export const runCheckCount = (data: RunConversations): number =>
  new Set(checkResults(data).map((rule) => rule.rule_id)).size;

/** The checks as the run graded them, from the copy each result keeps, so later edits do not show. */
export const runChecks = (data: RunConversations): ScenarioCheck[] => {
  const byId = new Map<string, unknown>();
  for (const rule of checkResults(data)) {
    const stored = rule.details?.rule;
    if (!byId.has(rule.rule_id) && stored && typeof stored === "object") byId.set(rule.rule_id, stored);
  }
  return parseChecks({ checks: [...byId.values()] }).checks;
};

/** The slots a column of tallies needs: passed and failed always, not evaluated when any has it. */
export const tallySlots = (counts: (ConversationCounts | null | undefined)[]): Verdict[] =>
  counts.some((item) => item?.not_evaluated) ? ["passed", "failed", "not_evaluated"] : ["passed", "failed"];

/** "3 of 5 conversations passed · 1 failed · 1 not evaluated". */
export const conversationsVerdictText = (counts: ConversationCounts): string => {
  if (!counts.passed && !counts.failed) {
    return `Nothing could be evaluated in ${plural(counts.total, "conversation")}`;
  }
  const parts = [`${counts.passed} of ${plural(counts.total, "conversation")} passed`];
  if (counts.failed) parts.push(`${counts.failed} failed`);
  if (counts.not_evaluated) parts.push(`${counts.not_evaluated} not evaluated`);
  return parts.join(" · ");
};

const VERDICT_LABELS: Record<Verdict, string> = { passed: "Passed", failed: "Failed", not_evaluated: "Not evaluated" };

export const verdictLabel = (verdict: Verdict): string => VERDICT_LABELS[verdict] ?? VERDICT_LABELS.not_evaluated;

const VERDICT_ORDER: Verdict[] = ["failed", "not_evaluated", "passed"];

/** What needs attention first: failed, then not evaluated, then passed, each in run order. */
export const reviewOrder = (conversations: RunConversationResult[]): RunConversationResult[] =>
  VERDICT_ORDER.flatMap((verdict) => conversations.filter((conversation) => conversation.verdict === verdict));

/** One name per conversation, from its opening message, as the dataset page names it. */
export const runConversationLabels = (conversations: RunConversationResult[]): Map<string, string> => {
  const shortId = (key: string) => key.slice(-6);
  const labelled = conversations.map((conversation) => ({
    key: conversation.key,
    label: labelFromMessage(conversation.turns[0]?.message ?? "", `Conversation #${shortId(conversation.key)}`),
  }));
  const counts = new Map<string, number>();
  labelled.forEach(({ label }) => counts.set(label, (counts.get(label) ?? 0) + 1));
  return new Map(
    labelled.map(({ key, label }) => [key, (counts.get(label) ?? 0) > 1 ? `${label} #${shortId(key)}` : label]),
  );
};

/** One thing a turn or conversation was graded on, in plain words. */
export interface GradedItem {
  key: string;
  status: Verdict;
  title: string;
  /** The technical name, kept for the detail. */
  method?: string;
  expected?: string | null;
  actual?: string | null;
  /** Why it was not evaluated, or the method's own comment. */
  note?: string | null;
  /** For a whole-conversation check: the turns it points at, and what each did. */
  turns?: number[];
  facts?: string[];
  /** It held on every turn or happened on none, so its sentence says all there is to say. */
  saysItAll?: boolean;
  /** It counts across the conversation, so the count is worth saying beside the turns. */
  counted?: boolean;
  /** It claims something of every turn ("every turn" or "never") rather than of one. */
  everywhere?: boolean;
  /** The turns it read; older runs did not keep them. */
  checked?: number[];
  /** It reads the expected reply, so a turn without one is not read. */
  readsExpected?: boolean;
  /** It reads turn by turn, unlike a count or a grade of the whole conversation. */
  byTurn?: boolean;
  /** What each turn it read did, in the order of those turns. */
  checkedFacts?: string[];
  /** Graded by the AI grader, whose reason is worth reading. */
  graded?: boolean;
  /** The check as the run graded it. */
  check?: ScenarioCheck;
  /** A whole-conversation check shown on one of its turns. */
  whole?: boolean;
  items?: GradedItem[];
}

const detailsOf = (rule: TestToolRuleResult): ToolRuleResultDetails & Record<string, unknown> =>
  (rule.details ?? {}) as ToolRuleResultDetails & Record<string, unknown>;

/** What a rule row expected, in its own words. */
export const ruleExpectedText = (rule: TestToolRuleResult): string => {
  const details = detailsOf(rule);
  return rule.technique === "tool_used" ? toolExpectedText(details) : (details.expected ?? "");
};

/** What a rule row saw. */
export const ruleActualText = (rule: TestToolRuleResult): string => {
  const details = detailsOf(rule);
  if (rule.technique === "tool_used") return toolActualText(details, rule.status);
  return details.comment ?? details.observed ?? "";
};

const checkItem = (rule: TestToolRuleResult): GradedItem => {
  const details = detailsOf(rule);
  const turns = Array.isArray(details.turns) ? (details.turns as number[]) : undefined;
  const facts = Array.isArray(details.facts) ? (details.facts as string[]) : undefined;
  const checked = Array.isArray(details.checked) ? (details.checked as number[]) : undefined;
  const checkedFacts = Array.isArray(details.checked_facts) ? (details.checked_facts as string[]) : undefined;
  // Said from the check itself, so older runs read the same; a turn's check as written, a conversation's without it.
  const [snapshot] = parseChecks({ checks: [details.rule] }).checks;
  const sentence = snapshot && (rule.scope === "turn" ? checkSentence(snapshot) : conversationSentence(snapshot));
  const stored = (details.rule ?? {}) as { min_calls?: number | null; max_calls?: number | null };
  // "Every turn" and "never" claim something of all turns; "at some point" of one.
  const everywhere = details.when === "every_turn" || details.expect === "should_not";
  // A grader's reason is worth reading either way.
  const graded = typeof details.score === "number";
  return {
    key: rule.id,
    status: rule.status,
    title: sentence || details.expected || details.rule_summary || "Check",
    actual: rule.status === "not_evaluated" ? null : (details.observed ?? null),
    note: rule.status === "not_evaluated" ? (details.comment ?? "This check could not be graded.") : null,
    turns,
    facts,
    // Only a check read over turns can hold on all of them; a turn's own check has no "when".
    saysItAll: Boolean(details.when) && !graded && (everywhere ? rule.status === "passed" : rule.status === "failed"),
    counted: stored.min_calls != null || stored.max_calls != null,
    everywhere: Boolean(details.when) && everywhere,
    checked,
    checkedFacts,
    graded,
    check: snapshot,
    readsExpected: readsExpectedReply(rule),
    byTurn:
      Boolean(details.when) &&
      !(stored.min_calls != null || stored.max_calls != null) &&
      !(graded && details.when !== "every_turn"),
    whole: rule.scope !== "turn",
  };
};

export interface CheckDetail {
  /** A sentence of its own, such as a grader's reason or "Holds on every turn." */
  text: string | null;
  /** Says what the turns are, such as "Holds here". */
  lead: string | null;
  turns: number[];
  facts: string[];
  /** Said after the turns, such as which turns it could not check and why. */
  rest?: string | null;
}

/** "Turn 2", "Turns 2–3" or "Turns 2, 5": runs of turns in few words. */
const turnSpans = (numbers: number[]): string => {
  const spans: string[] = [];
  numbers.forEach((number, index) => {
    if (index > 0 && number === numbers[index - 1] + 1) {
      const start = spans.pop()?.split("–")[0];
      spans.push(`${start}–${number}`);
    } else spans.push(String(number));
  });
  return `${numbers.length === 1 ? "Turn" : "Turns"} ${spans.join(", ")}`;
};

/** Which turns a check could not read, so a check of every turn does not seem to be about one. */
const unreadNote = (item: GradedItem, turnCount?: number): string | null => {
  // A turn with no expected reply is not one a check against it is about, so it goes unmentioned.
  if (!item.checked || turnCount === undefined || item.readsExpected) return null;
  const read = new Set(item.checked);
  const unread = Array.from({ length: turnCount }, (_, index) => index + 1).filter((number) => !read.has(number));
  return unread.length ? `${turnSpans(unread)} could not be checked.` : null;
};

/** What a whole-conversation check's row says under its sentence: where it held or broke, with the turns to jump to. */
export const checkDetail = (item: GradedItem, turnCount?: number): CheckDetail => {
  const none = { text: null, lead: null, turns: [], facts: [] };
  if (item.status === "not_evaluated") return { ...none, text: item.note ?? null };
  const turns = item.turns ?? [];
  if (turns.length) {
    // A count is worth saying beside the turns where it was counted.
    const lead = item.counted ? "On these turns" : item.status === "passed" ? "Holds here" : "Doesn't hold here";
    const rest = item.counted ? null : unreadNote(item, turnCount);
    return { text: item.counted ? (item.actual ?? null) : null, lead, turns, facts: item.facts ?? [], rest };
  }
  if (item.saysItAll) {
    // Some turns could not be read, so it names the ones it did instead of claiming every turn.
    const partly = item.checked && turnCount !== undefined && item.checked.length < turnCount && !item.readsExpected;
    if (partly && item.checked) {
      const lead = item.status === "passed" ? "Holds on every turn it could check" : "No turn it could check has this";
      return { ...none, lead, turns: item.checked, rest: unreadNote(item, turnCount) };
    }
    return { ...none, text: item.status === "passed" ? "Holds on every turn." : "No turn has this." };
  }
  return { ...none, text: item.actual ?? null };
};

// What a check says when it could not read every turn.
const PARTLY_READ = /could not be checked|turns? checked/;

/** The turns a whole-conversation check read; for older runs, every turn that ran unless it said otherwise. */
const turnsRead = (item: GradedItem, conversation: RunConversationResult): number[] => {
  if (item.checked) return item.checked;
  if (!item.byTurn || PARTLY_READ.test(item.actual ?? "")) return item.turns ?? [];
  return conversation.turns
    .filter((turn) => turn.status !== "execution_failed" && turn.status !== "skipped")
    .filter((turn) => !item.readsExpected || Boolean(turn.expected))
    .map((turn) => turn.number);
};

/**
 * What a turn the check did not name did: kept with the result, or for older runs said from the check,
 * since there an "every turn" or "never" check held and an "at some point" one did not happen.
 */
const unnamedFact = (item: GradedItem, number: number): string | null => {
  const kept = item.checkedFacts?.[item.checked?.indexOf(number) ?? -1];
  if (kept) return kept;
  if (!item.check || item.graded) return null;
  return turnFact(item.check, item.everywhere ? item.check.expect === "should" : false);
};

/** Why an "at some point" check no turn met counts against a turn. */
const elsewhere = (item: GradedItem): string | null =>
  !item.everywhere && item.status === "failed" ? "No reply did." : null;

/** The whole-conversation checks on this turn: each one it read either held or broke here, with what this turn did. */
export const conversationChecksOnTurn = (conversation: RunConversationResult, number: number): GradedItem[] =>
  conversation.rules.map(rowItem).flatMap((item) => {
    if (item.status === "not_evaluated") return [];
    const index = item.turns?.indexOf(number) ?? -1;
    const read = index >= 0 || turnsRead(item, conversation).includes(number);
    if (!read) return [];
    // An "at some point" check that was met belongs to the turns where it was met, not to the others.
    if (index < 0 && !item.everywhere && item.status === "passed") return [];
    // A listed turn is where it broke or was met. Any other turn did not break an "every turn" or
    // "never" check, and failed an "at some point" check no turn met.
    const status: Verdict =
      index >= 0 ? (item.status === "passed" ? "passed" : "failed") : item.everywhere ? "passed" : item.status;
    return [
      {
        ...item,
        key: `${item.key}-${number}`,
        status,
        method: "Whole conversation",
        // What this turn did; where it is not one the check named, why an "at some point" check counts here.
        actual: index >= 0 ? (item.facts?.[index] ?? null) : unnamedFact(item, number),
        note: index >= 0 ? null : elsewhere(item),
        turns: undefined,
        facts: undefined,
        checked: undefined,
        checkedFacts: undefined,
        whole: true,
      },
    ];
  });

/** A whole-conversation check that failed on this turn, with what this turn did. */
export const failedOnTurn = (conversation: RunConversationResult, number: number): GradedItem[] =>
  conversationChecksOnTurn(conversation, number).filter((item) => item.status === "failed");

const ruleItem = (rule: TestToolRuleResult): GradedItem => {
  const details = detailsOf(rule);
  return {
    key: rule.id,
    status: rule.status,
    title: details.rule_summary || methodLabel(rule.technique),
    method: methodLabel(rule.technique),
    expected: rule.status === "not_evaluated" ? null : ruleExpectedText(rule),
    actual: rule.status === "not_evaluated" ? null : ruleActualText(rule),
    note: rule.status === "not_evaluated" ? ruleActualText(rule) || null : null,
  };
};

/** A rule row as a graded item: a check reads as its sentence, an older rule as its summary. */
export const rowItem = (rule: TestToolRuleResult): GradedItem =>
  rule.technique === "checks" ? checkItem(rule) : ruleItem(rule);

const metricStatus = (metric: TestResultMetric): Verdict =>
  metric.not_evaluated || metric.error ? "not_evaluated" : metric.passed ? "passed" : "failed";

interface JudgeRuleDetail {
  label?: string;
  passed?: boolean;
  not_evaluated?: boolean;
  error?: boolean;
  reason?: string;
  comment?: string | null;
}

const judgeRuleStatus = (rule: JudgeRuleDetail): Verdict =>
  rule.error || rule.not_evaluated ? "not_evaluated" : rule.passed ? "passed" : "failed";

const metricItem = (technique: string, metric: TestResultMetric): GradedItem => {
  const item: GradedItem = {
    key: technique,
    status: metricStatus(metric),
    title: methodLabel(technique),
    method: methodLabel(technique),
    expected: metric.expected ?? null,
    actual: metric.actual ?? null,
    note: metric.comment ?? null,
  };
  const rules = technique === "llm_judge" && Array.isArray(metric.details) ? (metric.details as JudgeRuleDetail[]) : [];
  // One rubric reads as the method itself; several are listed under it.
  if (rules.length === 1) {
    const [rule] = rules;
    return { ...item, expected: rule.label ?? null, actual: rule.reason ?? null };
  }
  if (rules.length > 1) {
    item.items = rules.map((rule, index) => {
      const status = judgeRuleStatus(rule);
      return {
        key: `${technique}-${index}`,
        status,
        title: rule.label || `Rule ${index + 1}`,
        actual: status === "not_evaluated" ? null : (rule.reason ?? null),
        note: status === "not_evaluated" ? (rule.comment ?? null) : null,
      };
    });
  }
  return item;
};

/** The plain questions the older methods answer; their names stay in the detail. */
export const QUESTIONS: { key: string; label: string; techniques: string[] }[] = [
  {
    key: "answer",
    label: "Is the answer correct?",
    techniques: ["exact_match", "contains", "json_match", "field_equals", "llm_judge"],
  },
  {
    key: "path",
    label: "Did it use the right tools and route?",
    techniques: ["tool_used", "route_taken", "action_taken"],
  },
  { key: "grounded", label: "Is it grounded in the evidence?", techniques: ["nli_eval", "provenance_eval"] },
  { key: "avoids", label: "Does it avoid what it must not say?", techniques: ["not_contains"] },
  { key: "errors", label: "Did it run without errors?", techniques: ["no_errors"] },
];

export interface QuestionResult {
  key: string;
  label: string;
  status: Verdict;
  items: GradedItem[];
}

const groupStatus = (items: GradedItem[]): Verdict => {
  if (items.some((item) => item.status === "failed")) return "failed";
  if (items.some((item) => item.status === "passed")) return "passed";
  return "not_evaluated";
};

/** A turn's older methods and rules, under the question each answers. */
export const turnQuestions = (turn: RunTurnResult): QuestionResult[] => {
  const items = new Map<string, GradedItem[]>();
  const add = (technique: string, item: GradedItem) => {
    const question = QUESTIONS.find((entry) => entry.techniques.includes(technique))?.key ?? "answer";
    items.set(question, [...(items.get(question) ?? []), item]);
  };
  Object.entries(turn.metrics ?? {}).forEach(([technique, metric]) => add(technique, metricItem(technique, metric)));
  turn.rules.filter((rule) => rule.technique !== "checks").forEach((rule) => add(rule.technique, ruleItem(rule)));
  return QUESTIONS.filter((question) => items.has(question.key)).map((question) => {
    const grouped = items.get(question.key) ?? [];
    return { key: question.key, label: question.label, status: groupStatus(grouped), items: grouped };
  });
};

/** A turn's Should / Should not checks. */
export const turnChecks = (turn: RunTurnResult): GradedItem[] =>
  turn.rules.filter((rule) => rule.technique === "checks").map(checkItem);

const readsExpectedReply = (rule: TestToolRuleResult): boolean => {
  const details = detailsOf(rule);
  const snapshot = (details.rule ?? {}) as { context?: unknown; value?: unknown };
  // A value in the run with no value of its own is compared with the expected reply.
  const valueAgainstReply = details.kind === "value_equals" && (snapshot.value == null || snapshot.value === "");
  return (
    rule.technique === "checks" &&
    (details.kind === "reply_matches" || snapshot.context === "expected_reply" || valueAgainstReply)
  );
};

/** What failed in a conversation, one short line each, in turn order. */
export const conversationFindings = (conversation: RunConversationResult): string[] => {
  const lines: string[] = [];
  for (const turn of conversation.turns) {
    const prefix = `Turn ${turn.number}`;
    if (turn.status === "execution_failed") lines.push(`${prefix}: the turn did not finish`);
    turnChecks(turn)
      .filter((item) => item.status === "failed")
      .forEach((item) => lines.push(`${prefix}: ${item.title}`));
    for (const question of turnQuestions(turn).filter((entry) => entry.status === "failed")) {
      // A rule names what failed in its own sentence; a method is named by its question.
      const sentences = question.items
        .filter((item) => item.status === "failed" && item.title !== item.method)
        .map((item) => `${prefix}: ${item.title}`);
      lines.push(...(sentences.length ? sentences : [`${prefix}: ${question.label}`]));
    }
  }
  conversation.rules
    .map(rowItem)
    .filter((item) => item.status === "failed")
    .forEach((item) => lines.push(item.title));
  return lines;
};

/** Why a conversation was not evaluated: a turn that did not run or a check that could not be graded, else the first that says. */
export const notEvaluatedReason = (conversation: RunConversationResult, gradingError?: string | null): string => {
  for (const turn of conversation.turns) {
    if (turn.status && turn.status !== "scored" && turn.reason) return `Turn ${turn.number}: ${turn.reason}`;
  }
  // A check whose grading broke is what kept the conversation from passing.
  const broken = conversation.rules.find((rule) => detailsOf(rule).error);
  if (broken) return rowItem(broken).note ?? "A check could not be graded.";
  for (const turn of conversation.turns) {
    const row = turn.rules.find((rule) => detailsOf(rule).error);
    if (row) return `Turn ${turn.number}: ${rowItem(row).note ?? "A check could not be graded."}`;
  }
  const note = conversation.rules.map(rowItem).find((item) => item.note)?.note;
  if (note) return note;
  const turn = conversation.turns.find((entry) => entry.reason);
  if (turn) return `Turn ${turn.number}: ${turn.reason}`;
  return gradingError ?? "Nothing checks this conversation.";
};

/** How a turn's or conversation's checks went, counting each older method under its question too. */
export interface CheckTally {
  passed: number;
  failed: number;
  notEvaluated: number;
  total: number;
}

export const tallyItems = (items: GradedItem[], questions: QuestionResult[] = []): CheckTally => {
  const all = [...items, ...questions.flatMap((question) => question.items)];
  const count = (status: Verdict) => all.filter((item) => item.status === status).length;
  return { passed: count("passed"), failed: count("failed"), notEvaluated: count("not_evaluated"), total: all.length };
};

/** Every check graded in a conversation, on the whole of it and on each turn, as counts. */
export const conversationCheckCounts = (conversation: RunConversationResult): ConversationCounts => {
  const tally = tallyItems(
    [...conversation.rules.map(rowItem), ...conversation.turns.flatMap(turnChecks)],
    conversation.turns.flatMap(turnQuestions),
  );
  return { total: tally.total, passed: tally.passed, failed: tally.failed, not_evaluated: tally.notEvaluated };
};

/** "3 checks passed", "1 of 3 checks failed" or "Not evaluated"; null when nothing was checked. */
export const tallyText = (tally: CheckTally): string | null => {
  if (!tally.total) return null;
  if (tally.failed) {
    return tally.failed === tally.total
      ? `${plural(tally.failed, "check")} failed`
      : `${tally.failed} of ${plural(tally.total, "check")} failed`;
  }
  if (tally.notEvaluated === tally.total) return "Not evaluated";
  const passed = `${plural(tally.passed, "check")} passed`;
  return tally.notEvaluated ? `${passed} · ${tally.notEvaluated} not evaluated` : passed;
};

/** Everything that graded a turn: its checks, whole-conversation checks that failed on it, and older methods. */
export const turnGrading = (
  turn: RunTurnResult,
  conversation: RunConversationResult,
): { items: GradedItem[]; questions: QuestionResult[] } => ({
  items: [...turnChecks(turn), ...conversationChecksOnTurn(conversation, turn.number)],
  questions: turnQuestions(turn),
});

/** How a reply went, counting the whole-conversation checks on it as well as its own. */
export const replyVerdict = (turn: RunTurnResult, conversation: RunConversationResult): Verdict => {
  // A turn that did not finish, or failed by itself, keeps its own verdict.
  if (turn.status === "execution_failed" || turn.verdict === "failed") return turn.verdict;
  const { items, questions } = turnGrading(turn, conversation);
  const tally = tallyItems(items, questions);
  if (tally.failed) return "failed";
  return tally.passed ? "passed" : turn.verdict;
};

/** Whether anything graded a turn, so a turn nothing checks stays neutral. */
export const isGradedTurn = (turn: RunTurnResult): boolean =>
  turn.rules.length > 0 || Object.keys(turn.metrics ?? {}).length > 0;

export type Change =
  | "newly_failing"
  | "still_failing"
  | "no_longer_evaluated"
  | "fixed"
  | "newly_passing"
  | "one_run_only"
  | "unchanged";
export type ComparisonVerdict = "better" | "worse" | "mixed" | "same";

export interface ConversationChange {
  key: string;
  change: Change;
  before: Verdict | null;
  after: Verdict | null;
  /** The conversation as this run has it, or as the earlier run had it when it is gone. */
  conversation: RunConversationResult;
  /** Its checks that now pass or now fail, when it is in both runs. */
  checks: CheckMoves;
}

export interface CheckMoves {
  better: number;
  worse: number;
}

/** Checks that moved while the conversation's result stayed the same, which the result alone would hide. */
export const hiddenCheckMoves = (change: ConversationChange): boolean =>
  change.before === change.after && (change.checks.better > 0 || change.checks.worse > 0);

/** "3 checks now pass, 1 now fails." */
export const checkMovesText = ({ better, worse }: CheckMoves): string =>
  [
    better && `${better} check${better === 1 ? "" : "s"} now pass${better === 1 ? "es" : ""}`,
    worse && `${worse} now fail${worse === 1 ? "s" : ""}`,
  ]
    .filter(Boolean)
    .join(", ") + ".";

export interface RunComparison {
  verdict: ComparisonVerdict;
  changes: ConversationChange[];
  /** Checks that moved where the conversation's result stayed the same, together: what the rows' pills add up to. */
  checks: CheckMoves;
  /** No conversation changed result, so the verdict comes from the checks. */
  fromChecks: boolean;
  /** Conversations graded in the earlier run and not in this one, by how they went then. */
  noLongerEvaluated: { passed: number; failed: number };
}

/** A conversation's checks that now pass or now fail, as the compare tables highlight them. */
const checkMoves = (
  earlier: RunConversationResult | undefined,
  later: RunConversationResult | undefined,
): CheckMoves => {
  const pairs = [
    ...pairChecks(earlier, later),
    ...pairTurnChecks(earlier, later).map((row) => ({ before: row.before?.item, after: row.after?.item })),
  ];
  const moves = pairs.map(pairChange);
  return {
    better: moves.filter((move) => move === "better").length,
    worse: moves.filter((move) => move === "worse").length,
  };
};

const classify = (before: Verdict | null, after: Verdict | null): Change => {
  if (before === null || after === null) return "one_run_only";
  if (before === after) return before === "failed" ? "still_failing" : "unchanged";
  if (after === "failed") return "newly_failing";
  if (after === "passed") return before === "failed" ? "fixed" : "newly_passing";
  return "no_longer_evaluated";
};

/** Each conversation's change since an earlier run, matched by conversation. */
export const compareRuns = (baseline: RunConversations, current: RunConversations): RunComparison => {
  const before = new Map(baseline.conversations.map((conversation) => [conversation.key, conversation]));
  const keys = new Set(current.conversations.map((conversation) => conversation.key));
  const none: CheckMoves = { better: 0, worse: 0 };
  const changes: ConversationChange[] = current.conversations.map((conversation) => {
    const earlier = before.get(conversation.key);
    const previous = earlier?.verdict ?? null;
    return {
      key: conversation.key,
      change: classify(previous, conversation.verdict),
      before: previous,
      after: conversation.verdict,
      conversation,
      checks: earlier ? checkMoves(earlier, conversation) : none,
    };
  });
  baseline.conversations
    .filter((conversation) => !keys.has(conversation.key))
    .forEach((conversation) =>
      changes.push({
        key: conversation.key,
        change: "one_run_only",
        before: conversation.verdict,
        after: null,
        conversation,
        checks: none,
      }),
    );
  // The verdict counts what the four cards count, and passes lost to not being evaluated, which the header lists.
  const groups = new Set(changes.map(compareGroup));
  const lost = changes.filter((change) => change.change === "no_longer_evaluated");
  const noLongerEvaluated = {
    passed: lost.filter((change) => change.before === "passed").length,
    failed: lost.filter((change) => change.before === "failed").length,
  };
  // A conversation that passed and is not evaluated now no longer passes, so the run can't be the same.
  const worse = groups.has("newly_failing") || noLongerEvaluated.passed > 0;
  const better = groups.has("newly_passing");
  const byConversation: ComparisonVerdict = worse && better ? "mixed" : worse ? "worse" : better ? "better" : "same";
  // A conversation that changed result is on its card already; only what that would hide is counted.
  const checks = changes
    .filter(hiddenCheckMoves)
    .reduce(
      (sum, change) => ({ better: sum.better + change.checks.better, worse: sum.worse + change.checks.worse }),
      none,
    );
  // "Same" only when nothing changed: with every conversation where it was, the checks decide.
  const fromChecks = byConversation === "same" && (checks.better > 0 || checks.worse > 0);
  const verdict: ComparisonVerdict = fromChecks
    ? checks.better && checks.worse
      ? "mixed"
      : checks.worse
        ? "worse"
        : "better"
    : byConversation;
  return { verdict, changes, checks, fromChecks, noLongerEvaluated };
};

/** The four ways a conversation can go between two runs, and the rest that cannot be compared. */
export type CompareGroup = "newly_failing" | "still_failing" | "newly_passing" | "still_passing" | "not_compared";

/** What needs attention first; each says how it went as before and after. */
export const COMPARE_GROUPS: {
  group: Exclude<CompareGroup, "not_compared">;
  title: string;
  before: Verdict;
  after: Verdict;
}[] = [
  { group: "newly_failing", title: "Newly failing", before: "passed", after: "failed" },
  { group: "still_failing", title: "Still failing", before: "failed", after: "failed" },
  { group: "newly_passing", title: "Newly passing", before: "failed", after: "passed" },
  { group: "still_passing", title: "Still passing", before: "passed", after: "passed" },
];

/** Where a conversation's change is counted: passing or failing in both runs, or newly so; else not compared. */
export const compareGroup = (change: ConversationChange): CompareGroup => {
  switch (change.change) {
    case "newly_failing":
    case "still_failing":
      return change.change;
    case "fixed":
    case "newly_passing":
      return "newly_passing";
    case "unchanged":
      return change.after === "passed" ? "still_passing" : "not_compared";
    default:
      return "not_compared";
  }
};

/** Why a conversation was not compared, naming the runs. */
export const notComparedReason = (change: ConversationChange, beforeName: string, afterName: string): string => {
  if (!change.after) return `Only in ${beforeName}.`;
  if (!change.before) return `Only in ${afterName}.`;
  // A run that newly evaluates a conversation counts it as newly passing or failing, so only these are left.
  return change.before === "not_evaluated" ? "Not evaluated in either run." : `Not evaluated in ${afterName}.`;
};

const createdAt = (run: TestRun): number => new Date(run.created_at ?? 0).getTime();

/** Two runs as before and after, so a comparison reads forward in time. */
export const inTimeOrder = (first: TestRun, second: TestRun): [TestRun, TestRun] =>
  createdAt(first) <= createdAt(second) ? [first, second] : [second, first];

/** A comparison's conversations in the order its lists show them: by group, each as the run played them. */
export const comparisonOrder = (comparison: RunComparison): ConversationChange[] => {
  const groups: CompareGroup[] = [...COMPARE_GROUPS.map((entry) => entry.group), "not_compared"];
  return groups.flatMap((group) => comparison.changes.filter((change) => compareGroup(change) === group));
};

/** The turns of one conversation in two runs, matched by the dataset turn they played, in the later run's order. */
export const pairTurns = (
  earlier: RunConversationResult | undefined,
  later: RunConversationResult | undefined,
): { key: string; before?: RunTurnResult; after?: RunTurnResult }[] => {
  const beforeTurns = new Map((earlier?.turns ?? []).map((turn) => [turn.case_id, turn]));
  const pairs: { key: string; before?: RunTurnResult; after?: RunTurnResult }[] = (later?.turns ?? []).map((turn) => ({
    key: turn.case_id,
    before: beforeTurns.get(turn.case_id),
    after: turn,
  }));
  const seen = new Set(pairs.map((pair) => pair.key));
  (earlier?.turns ?? [])
    .filter((turn) => !seen.has(turn.case_id))
    .forEach((turn) => pairs.push({ key: turn.case_id, before: turn }));
  return pairs;
};

export interface PairedCheck {
  key: string;
  title: string;
  before?: GradedItem;
  after?: GradedItem;
}

/** Each turn check of a conversation, with the turn it is on. */
export const turnCheckRows = (conversation: RunConversationResult): { item: GradedItem; turn: number }[] =>
  conversation.turns.flatMap((turn) => turnChecks(turn).map((item) => ({ item, turn: turn.number })));

/** What a turn check's row says: its one turn, as a link, and why it could not be checked there. */
export const turnCheckDetail = (item: GradedItem, turn: number): CheckDetail => ({
  text: item.status === "not_evaluated" ? (item.note ?? null) : null,
  lead: null,
  turns: [turn],
  facts: [item.actual ?? ""],
});

export interface PairedTurnCheck {
  key: string;
  title: string;
  before?: { item: GradedItem; turn: number };
  after?: { item: GradedItem; turn: number };
}

/** One conversation's turn checks in two runs, matched by check. */
export const pairTurnChecks = (
  earlier: RunConversationResult | undefined,
  later: RunConversationResult | undefined,
): PairedTurnCheck[] => {
  const rows = new Map<string, PairedTurnCheck>();
  const add = (conversation: RunConversationResult | undefined, side: "before" | "after") => {
    if (!conversation) return;
    for (const row of turnCheckRows(conversation)) {
      const key = `${row.item.title}:${row.turn}`;
      const paired = rows.get(key) ?? { key, title: row.item.title };
      paired[side] = row;
      rows.set(key, paired);
    }
  };
  add(earlier, "before");
  add(later, "after");
  return [...rows.values()];
};

/** Said of this reply: "The reply mentioned…" reads "This reply mentioned…". */
export const ofThisReply = (fact: string): string => fact.replace(/^The reply\b/, "This reply");

/** The checks on one reply in two runs, matched by check. */
export interface ReplyCheckPair {
  key: string;
  title: string;
  whole: boolean;
  before?: GradedItem;
  after?: GradedItem;
}

/** How a check on a reply moved: worse, better, otherwise changed, or null when it is the same or on one side only. */
export const pairChange = (pair: Pick<ReplyCheckPair, "before" | "after">): "worse" | "better" | "changed" | null => {
  const { before, after } = pair;
  if (!before || !after || before.status === after.status) return null;
  if (after.status === "failed") return "worse";
  return after.status === "passed" && before.status === "failed" ? "better" : "changed";
};

const PAIR_RANK = { worse: 0, better: 1, changed: 2 } as const;
const STATUS_RANK: Record<Verdict, number> = { failed: 3, not_evaluated: 4, passed: 5 };

/** One reply's checks in two runs: those that got worse first, then better, then the rest by how they went. */
export const pairReplyChecks = (
  before: { turn: RunTurnResult; conversation: RunConversationResult } | undefined,
  after: { turn: RunTurnResult; conversation: RunConversationResult } | undefined,
): ReplyCheckPair[] => {
  const rows = new Map<string, ReplyCheckPair>();
  const add = (side: typeof before, at: "before" | "after") => {
    if (!side) return;
    for (const item of turnGrading(side.turn, side.conversation).items) {
      const whole = item.whole !== false;
      const key = `${whole ? "whole" : "turn"}:${item.title}`;
      const row = rows.get(key) ?? { key, title: item.title, whole };
      row[at] = item;
      rows.set(key, row);
    }
  };
  add(before, "before");
  add(after, "after");
  const rank = (row: ReplyCheckPair) => {
    const change = pairChange(row);
    return change ? PAIR_RANK[change] : STATUS_RANK[(row.after ?? row.before)?.status ?? "passed"];
  };
  return [...rows.values()].sort((a, b) => rank(a) - rank(b));
};

/** For each check, the turns where it went differently in two runs, by each run's own turn numbers. */
export const changedTurnsByCheck = (
  earlier: RunConversationResult | undefined,
  later: RunConversationResult | undefined,
): Map<string, { before: Set<number>; after: Set<number> }> => {
  const changed = new Map<string, { before: Set<number>; after: Set<number> }>();
  if (!earlier || !later) return changed;
  for (const { before, after } of pairTurns(earlier, later)) {
    if (!before || !after) continue;
    for (const pair of pairReplyChecks({ turn: before, conversation: earlier }, { turn: after, conversation: later })) {
      if (!pairChange(pair)) continue;
      const turns = changed.get(pair.key) ?? { before: new Set<number>(), after: new Set<number>() };
      turns.before.add(before.number);
      turns.after.add(after.number);
      changed.set(pair.key, turns);
    }
  }
  return changed;
};

/** One conversation's whole-conversation checks in two runs, matched by check. */
export const pairChecks = (
  earlier: RunConversationResult | undefined,
  later: RunConversationResult | undefined,
): PairedCheck[] => {
  const rows = new Map<string, PairedCheck>();
  const add = (conversation: RunConversationResult | undefined, side: "before" | "after") => {
    for (const rule of conversation?.rules ?? []) {
      const item = rowItem(rule);
      const key = `${rule.technique}:${rule.rule_id}`;
      const row = rows.get(key) ?? { key, title: item.title };
      row[side] = item;
      rows.set(key, row);
    }
  };
  add(earlier, "before");
  add(later, "after");
  return [...rows.values()];
};

/** The opening words of a message, for naming the reply it got. */
export const excerpt = (message: string, length = 80): string =>
  message.length > length ? `${message.slice(0, length).trimEnd()}…` : message;
