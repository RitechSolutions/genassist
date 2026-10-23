import type { TestCase } from "@/interfaces/testSuite.interface";
import type {
  CheckContext,
  CheckGrader,
  CheckKind,
  CheckLevel,
  CheckMatch,
  CheckToolRef,
  EvaluationToolCatalog,
  OlderMethods,
  ScenarioCheck,
} from "@/interfaces/testEvaluation.interface";
import { conversationLabels, groupCasesByConversation, turnLabel } from "./datasetConversations";
import { answerOf, hasExpected } from "./recordFields";

export const CHECKS_TECHNIQUE = "checks";

// Named after the older methods where their names were clear; the reply first, then tools and steps, then values.
export const CHECK_KINDS: { value: CheckKind; label: string; description: string }[] = [
  {
    value: "reply_mentions",
    label: "Contains",
    description: "The reply mentions words you list, or is exactly a text.",
  },
  {
    value: "reply_matches",
    label: "Matches the expected reply",
    description: "Each reply against the turn's expected reply in the dataset.",
  },
  { value: "reply_meets", label: "LLM judge", description: "A rule in plain words, graded by AI." },
  {
    value: "reply_grounded",
    label: "Sticks to the facts",
    description: "The reply only says what the knowledge base, the tool results or another source supports.",
  },
  { value: "tool_called", label: "Tool used", description: "An agent calls a tool, with given values if you want." },
  {
    value: "only_tools",
    label: "Allowed tools",
    description: "Only the tools on a list are used. With Should not, none of them is.",
  },
  { value: "step_runs", label: "Step ran", description: "A step of the workflow runs to the end." },
  { value: "step_fails", label: "Step failed", description: "A step of the workflow ends with an error." },
  { value: "route_taken", label: "Route taken", description: "A router or switch picks a branch." },
  { value: "state_equals", label: "Remembered value", description: "A value the workflow keeps between turns." },
  { value: "value_equals", label: "Field equals", description: "A value in the turn's inputs, output or steps." },
];

export const MATCH_MODES: { value: CheckMatch; label: string }[] = [
  { value: "meaning", label: "Same meaning (graded by AI)" },
  { value: "contains", label: "Contains it" },
  { value: "exact", label: "Exactly" },
];

export const MENTION_MODES: { value: CheckMatch; label: string }[] = [
  { value: "contains", label: "Mentions these words" },
  { value: "exact", label: "Is exactly this" },
];

/** What a rule's AI grader can also read. */
export const CONTEXTS: { value: CheckContext; label: string }[] = [
  { value: "expected_reply", label: "The expected reply" },
  { value: "knowledge_base", label: "The knowledge-base passages" },
  { value: "tool_calls", label: "The tool calls and results" },
  { value: "session", label: "The session values" },
  { value: "run_value", label: "A value in the run" },
];

/** What a reply can stick to. */
export const GROUNDS: { value: CheckContext; label: string }[] = [
  { value: "knowledge_base", label: "The knowledge base" },
  { value: "expected_reply", label: "The expected reply" },
  { value: "tool_calls", label: "The tool results" },
  { value: "session", label: "The session values" },
  { value: "run_value", label: "A value in the run" },
];

/** Each reply is graded against its own turn, so these hold on every turn they apply to. */
export const EVERY_TURN_KINDS = new Set<CheckKind>(["reply_matches", "reply_grounded"]);

export const PASS_SCORE = 0.5;

/** Whether the AI grader decides the check. */
export const isAiGraded = (check: ScenarioCheck): boolean =>
  check.kind === "reply_meets" ||
  (check.kind === "reply_grounded" && !check.grader) ||
  (check.kind === "reply_matches" && (check.match ?? "meaning") === "meaning");

/** Whether a score decides the check: the AI grader's, the NLI model's or text similarity's. */
export const isScored = (check: ScenarioCheck): boolean =>
  isAiGraded(check) || (check.kind === "reply_grounded" && Boolean(check.grader));

/** What grades a reply against its source, as NLI and Provenance did. */
export const GRADERS: { value: CheckGrader | null; label: string }[] = [
  { value: null, label: "The AI grader" },
  { value: "nli", label: "The NLI model" },
  { value: "similarity", label: "Text similarity" },
];

export const NLI_MODELS = [
  { value: "cross-encoder/nli-deberta-v3-base", label: "DeBERTa v3 Base" },
  { value: "cross-encoder/nli-roberta-base", label: "RoBERTa Base" },
];

export const EMBEDDING_TYPES = [
  { value: "huggingface", label: "Hugging Face" },
  { value: "openai", label: "OpenAI" },
  { value: "bedrock", label: "Amazon Bedrock" },
];

export const CHECK_LEVELS: { value: CheckLevel; label: string }[] = [
  { value: "every_conversation", label: "All conversations" },
  { value: "conversation", label: "Chosen conversations" },
  { value: "turn", label: "One turn" },
];

// ---- the dataset as checks see it ----

export interface CheckTurn {
  caseId: string;
  turnIndex: number | null;
  /** 1-based position among the conversation's current turns. */
  position: number;
  message: string;
  /** The dataset's expected reply, as text, when the turn has one. */
  expected?: string | null;
  /** The turn's other inputs, such as a region, as name and text. */
  inputs?: [string, string][];
}

export interface CheckConversation {
  /** What a check stores: the source conversation, or the case of a standalone turn, as the run groups them. */
  key: string;
  label: string;
  turns: CheckTurn[];
}

const messageOf = (entry: TestCase): string => {
  const message = entry.input_data?.message;
  return typeof message === "string" ? message : "";
};

const expectedOf = (entry: TestCase): string | null =>
  answerOf(entry.expected_output) ??
  (hasExpected(entry.expected_output) ? JSON.stringify(entry.expected_output) : null);

const inputsOf = (entry: TestCase): [string, string][] =>
  Object.entries(entry.input_data ?? {})
    .filter(([key]) => key !== "message")
    .map(([key, value]) => [key, typeof value === "string" ? value : JSON.stringify(value)]);

export const checkConversations = (cases: TestCase[]): CheckConversation[] => {
  const groups = groupCasesByConversation(cases);
  const labels = conversationLabels(groups);
  return groups
    .filter((group) => group.cases[0]?.id)
    .map((group) => ({
      key: group.conversationId ?? (group.cases[0].id as string),
      label: labels.get(group.key) ?? "",
      turns: group.cases.map((entry, index) => ({
        caseId: entry.id as string,
        turnIndex: entry.turn_index ?? null,
        position: index + 1,
        message: messageOf(entry),
        expected: expectedOf(entry),
        inputs: inputsOf(entry),
      })),
    }));
};

// ---- new checks ----

export interface CheckTarget {
  level: CheckLevel;
  /** The chosen conversations, for the conversation level. */
  conversations?: CheckConversation[];
  /** The turn's conversation, for the turn level. */
  conversation?: CheckConversation;
  turn?: CheckTurn;
}

const randomId = (): string =>
  globalThis.crypto?.randomUUID?.() ?? `${Date.now().toString(36)}${Math.random().toString(36).slice(2)}`;

/** The fields that point a check at its conversations or turn. */
export const targetFields = (target: CheckTarget): Partial<ScenarioCheck> => ({
  level: target.level,
  conversation_ids: target.level === "conversation" ? (target.conversations ?? []).map((item) => item.key) : null,
  conversation_id: target.level === "turn" ? (target.conversation?.key ?? null) : null,
  case_id: target.level === "turn" ? (target.turn?.caseId ?? null) : null,
  turn_index: target.level === "turn" ? (target.turn?.turnIndex ?? null) : null,
  turn_message: target.level === "turn" ? (target.turn?.message ?? null) : null,
});

/** What a check has picked where it applies, to give back if its place is chosen again. */
export const targetOf = (check: ScenarioCheck): Partial<ScenarioCheck> => ({
  conversation_ids: check.conversation_ids ?? null,
  conversation_id: check.conversation_id ?? null,
  case_id: check.case_id ?? null,
  turn_index: check.turn_index ?? null,
  turn_message: check.turn_message ?? null,
});

/** The fields for a new place: what was picked there before, else a picked turn's conversation. */
export const retarget = (
  check: ScenarioCheck,
  level: CheckLevel,
  conversations: CheckConversation[],
  remembered?: Partial<ScenarioCheck>,
): Partial<ScenarioCheck> => {
  if (level === "every_conversation") return targetFields({ level });
  if (remembered) return { ...targetFields({ level }), ...remembered, level };
  const turn = level === "conversation" && check.level === "turn" ? findCheckTurn(check, conversations) : null;
  return targetFields({ level, conversations: turn && !("problem" in turn) ? [turn.conversation] : [] });
};

/** The conversations a conversation-level check is about, including one stored the older way. */
export const chosenConversations = (check: ScenarioCheck): string[] =>
  check.level === "conversation"
    ? [
        ...new Set([...(check.conversation_ids ?? []), ...(check.conversation_id ? [check.conversation_id] : [])]),
      ].filter((key) => key.trim().length > 0)
    : [];

/** Whether a check says where it applies: all conversations, the chosen ones, or its turn. */
export const isPlaced = (check: ScenarioCheck): boolean => {
  if (check.level === "conversation") return chosenConversations(check).length > 0;
  if (check.level === "turn")
    return Boolean(check.case_id) || (Boolean(check.conversation_id) && check.turn_index != null);
  return true;
};

/** How many of a check's chosen conversations the dataset no longer has. */
export const goneConversations = (check: ScenarioCheck, conversations: CheckConversation[]): number =>
  chosenConversations(check).filter((key) => !conversations.some((item) => item.key === key)).length;

/** Said of a check that still has some of its chosen conversations, but not all. */
export const goneNote = (check: ScenarioCheck, conversations: CheckConversation[]): string | null => {
  const chosen = chosenConversations(check).length;
  const gone = goneConversations(check, conversations);
  if (!gone || gone === chosen) return null;
  const left = chosen - gone;
  const rest = left === 1 ? "the one left" : `the other ${left}`;
  return `${gone} of its ${chosen} conversations ${gone === 1 ? "is" : "are"} no longer in the dataset, so it checks ${rest}.`;
};

export const newCheck = (target: CheckTarget = { level: "every_conversation" }): ScenarioCheck => ({
  id: `check-${randomId()}`,
  expect: "should",
  kind: "reply_mentions",
  when: "anywhere",
  text: "",
  ...targetFields(target),
  level: target.level,
});

// ---- sentences: the same wording the backend stores with each result ----

const text = (value: unknown): string =>
  value !== null && typeof value === "object" ? JSON.stringify(value) : String(value ?? "").trim();
const filled = (value: unknown): boolean => text(value).length > 0;

export const toolName = (check: ScenarioCheck): string => text(check.tool_name || check.tool);
export const stepName = (check: ScenarioCheck): string => text(check.step_name || check.step);
export const routerName = (check: ScenarioCheck): string => text(check.router_name || check.router);
export const branchName = (check: ScenarioCheck): string => text(check.branch_label || check.branch);

/** Graded turn by turn rather than once over the conversation. */
export const isPerTurn = (check: ScenarioCheck): boolean =>
  EVERY_TURN_KINDS.has(check.kind) || check.level === "turn" || check.when === "every_turn";

const MATCH_VERBS: Record<CheckMatch, string> = {
  exact: "be exactly",
  contains: "contain",
  meaning: "say the same as",
};
const CONTEXT_PHRASES: Partial<Record<CheckContext, string>> = {
  expected_reply: ", graded with the expected reply",
  knowledge_base: ", graded with the knowledge-base passages",
  tool_calls: ", graded with the tool calls",
  session: ", graded with the session values",
};
const GROUND_PHRASES: Partial<Record<CheckContext, string>> = {
  expected_reply: "the expected reply",
  knowledge_base: "the knowledge base",
  tool_calls: "the tool results",
  session: "the session values",
};

const argPairs = (args: Record<string, string> | undefined): string =>
  Object.entries(args ?? {})
    .filter(([key]) => filled(key))
    .map(([key, value]) => `${key.trim()} = ${text(value)}`)
    .join(", ");

const joined = (items: string[], joiner: string): string =>
  items.length === 1 ? items[0] : `${items.slice(0, -1).join(", ")} ${joiner} ${items[items.length - 1]}`;

const quoted = (name: string): string => `"${name}"`;

const listed = (names: string[], joiner: string): string => joined(names.map(quoted), joiner);

const times = (count: number): string => (count === 1 ? "1 time" : `${count} times`);

const counts = (check: ScenarioCheck): string => {
  const low = check.min_calls ?? null;
  const high = check.max_calls ?? null;
  if (low != null && high != null) return low === high ? ` exactly ${times(low)}` : ` between ${low} and ${high} times`;
  if (low != null) return ` at least ${times(low)}`;
  if (high != null) return ` at most ${times(high)}`;
  return "";
};

const byAgent = (check: ScenarioCheck): string =>
  filled(check.agent_name) || filled(check.agent) ? ` by "${text(check.agent_name || check.agent)}"` : "";

const also = (check: ScenarioCheck): string => (filled(check.rubric) ? `, also: "${text(check.rubric)}"` : "");

const gradedBy = (check: ScenarioCheck): string => {
  if (check.grader === "nli")
    return `, graded by the NLI model${check.fail_on_contradiction ? ", failing any contradiction" : ""}`;
  return check.grader === "similarity" ? ", graded by text similarity" : "";
};

/**
 * Every tool a check is about: a tool check's own, with its values and result, and for what should happen its
 * others; or the list that may be used.
 */
export const toolRefs = (check: ScenarioCheck): CheckToolRef[] =>
  check.kind === "tool_called"
    ? [
        {
          tool: check.tool,
          tool_name: check.tool_name,
          args: check.args,
          result_not_empty: check.result_not_empty,
          result_contains: check.result_contains,
        },
        ...(check.expect === "should" ? (check.tools ?? []) : []),
      ]
    : (check.tools ?? []);

/** A tool by name, with what its own call should have, e.g. "lookup" (with id = 7, returning a result). */
const toolWithConditions = (ref: CheckToolRef): string => {
  const parts = argPairs(ref.args) ? [`with ${argPairs(ref.args)}`] : [];
  if (filled(ref.result_contains)) parts.push(`returning a result that contains "${text(ref.result_contains)}"`);
  else if (ref.result_not_empty) parts.push("returning a result");
  const name = `"${text(ref.tool_name || ref.tool)}"`;
  return parts.length ? `${name} (${parts.join(", ")})` : name;
};

/** A node type as words: "zendeskTicketNode" reads "Zendesk ticket", as the backend names it. */
export const stepTypeLabel = (type: string): string => {
  const words = type
    .replace(/Node$/, "")
    .replace(/(?!^)([A-Z])/g, " $1")
    .split(/\s+/)
    .filter(Boolean);
  const label = words.map((word) => word.toLowerCase()).join(" ") || type;
  return label.charAt(0).toUpperCase() + label.slice(1);
};

/** Any step of a node type, rather than one picked step. */
export const isStepType = (check: ScenarioCheck): boolean => filled(check.step_type) && !filled(check.step);

const clause = (check: ScenarioCheck, modal: string): string => {
  switch (check.kind) {
    case "reply_mentions":
      return check.match === "exact"
        ? `the reply ${modal} be exactly "${text(check.text)}"`
        : `the reply ${modal} mention "${text(check.text)}"`;
    case "reply_meets": {
      const rule = `${isPerTurn(check) ? "the reply" : "the agent"} ${modal} do this: "${text(check.rubric)}"`;
      if (!check.context || !isPerTurn(check)) return rule;
      if (check.context === "run_value") return `${rule}, graded with the value at "${text(check.context_path)}"`;
      return rule + (CONTEXT_PHRASES[check.context] ?? "");
    }
    case "reply_matches":
      return (
        `the reply ${modal} ${MATCH_VERBS[check.match ?? "meaning"]} the expected reply` +
        ((check.match ?? "meaning") === "meaning" ? also(check) : "")
      );
    case "reply_grounded": {
      const source = check.context ?? "knowledge_base";
      const grounds = GROUND_PHRASES[source] ?? `the value at "${text(check.context_path)}"`;
      return `the reply ${modal} stick to ${grounds}${gradedBy(check)}${check.grader ? "" : also(check)}`;
    }
    case "step_fails":
      if (modal === "should") return "a step should fail";
      return modal === "should never" ? "no step should ever fail" : "no step should fail";
    case "tool_called": {
      const refs = toolRefs(check);
      if (refs.length > 1) {
        // Each tool says its own values and result; the counts and success are over them all.
        const named = joined(refs.map(toolWithConditions), "or");
        const total = counts(check);
        return `one of the tools ${named} ${modal} be called${byAgent(check)}${total}${total ? " in all" : ""}${
          check.succeeds ? " and succeed" : ""
        }`;
      }
      let result = `the tool "${toolName(check)}" ${modal} be called${byAgent(check)}`;
      const pairs = argPairs(check.args);
      if (pairs) result += ` with ${pairs}`;
      // Counts, success and results only say more about what should happen.
      if (check.expect !== "should") return result;
      result += counts(check);
      if (check.succeeds) result += " and succeed";
      if (filled(check.result_contains))
        result += ` and return a result that contains "${text(check.result_contains)}"`;
      else if (check.result_not_empty) result += " and return a result";
      return result;
    }
    case "only_tools": {
      const names = (check.tools ?? []).map((ref) => text(ref.tool_name || ref.tool));
      if (check.expect === "should_not") {
        // The tools it may not use, each of them.
        if (!names.length) return `the tools on its list ${modal} be used${byAgent(check)}`;
        if (names.length === 1) return `the tool "${names[0]}" ${modal} be used${byAgent(check)}`;
        const ever = modal === "should never" ? " ever" : "";
        return `none of the tools ${listed(names, "and")} should${ever} be used${byAgent(check)}`;
      }
      if (!names.length) return `no tool ${modal} be used${byAgent(check)}`;
      const subject = names.length === 1 ? `only the tool "${names[0]}"` : `only the tools ${listed(names, "and")}`;
      const called = counts(check);
      const how = (check.succeeds ? " successfully" : "") + called;
      return `${subject} ${modal} be used${byAgent(check)}${called ? `, called${how}` : ""}`;
    }
    case "step_runs":
      return isStepType(check)
        ? `a step of type "${text(check.step_name || check.step_type)}" ${modal} run`
        : `the step "${stepName(check)}" ${modal} run`;
    case "route_taken":
      return filled(check.router) || filled(check.router_name)
        ? `the router "${routerName(check)}" ${modal} take "${branchName(check)}"`
        : `a router ${modal} take "${branchName(check)}"`;
    case "value_equals":
      return `the value at "${text(check.path)}" ${modal} be ${filled(check.value) ? `"${text(check.value)}"` : "the expected reply"}`;
    default:
      return `the remembered value "${text(check.key)}" ${modal} be "${text(check.value)}"`;
  }
};

/** A check read back as one sentence, e.g. 'The reply should never mention "RingGo".' */
// Capitalised, with no second full stop after a quote that already ends with one.
const asSentence = (sentence: string): string =>
  `${sentence.charAt(0).toUpperCase()}${sentence.slice(1)}${/[.!?]["”]?$/.test(sentence) ? "" : "."}`;

export const checkSentence = (check: ScenarioCheck): string => {
  const whole = check.level !== "turn";
  const once = whole && check.when !== "every_turn";
  const modal = check.expect === "should_not" ? (once ? "should never" : "should not") : "should";
  // The chosen conversations are named where the check is listed, so only every conversation says so.
  const every = check.level === "every_conversation";
  let prefix = "";
  if (EVERY_TURN_KINDS.has(check.kind)) {
    prefix = check.level === "turn" ? "" : "On every turn, ";
  } else if (whole) {
    if (check.when === "every_turn") prefix = "On every turn, ";
    else if (check.expect === "should" && check.kind !== "only_tools") {
      prefix = every ? "In every conversation, at some point, " : "At some point, ";
    } else if (every) prefix = "In every conversation, ";
  }
  let sentence = prefix + clause(check, modal);
  // As the backend writes it: six significant digits, only for a check graded with a score.
  if (isScored(check) && check.pass_score != null && check.pass_score !== PASS_SCORE) {
    sentence += ` (passes at ${Number(check.pass_score.toPrecision(6))})`;
  }
  return asSentence(sentence);
};

/**
 * What happened on one reply, said from the check, for runs that did not keep it:
 * whether the thing it looks for happened there ('The reply did not mention "Amazon".'), or null when it cannot be said.
 */
export const turnFact = (check: ScenarioCheck, happened: boolean): string | null => {
  const not = happened ? "" : " not";
  switch (check.kind) {
    case "reply_mentions":
      return check.match === "exact"
        ? `The reply was${not} exactly "${text(check.text)}".`
        : `The reply ${happened ? "mentioned" : "did not mention"} "${text(check.text)}".`;
    case "reply_matches":
      return check.match === "exact" ? `The reply was${not} exactly the expected reply.` : null;
    case "step_runs":
      return isStepType(check)
        ? `A step of type "${text(check.step_name || check.step_type)}" ${happened ? "ran" : "did not run"}.`
        : `The step "${stepName(check)}" ${happened ? "ran" : "did not run"}.`;
    case "route_taken":
      return `The router${filled(check.router) || filled(check.router_name) ? ` "${routerName(check)}"` : ""} ${
        happened ? "took" : "did not take"
      } "${branchName(check)}".`;
    case "state_equals":
      return `${text(check.key)} was${not} "${text(check.value)}".`;
    case "step_fails":
      return happened ? "A step failed." : "No step failed.";
    case "tool_called": {
      const names = toolRefs(check).map((ref) => text(ref.tool_name || ref.tool));
      return names.length === 1 ? `The tool "${names[0]}" was${not} called.` : null;
    }
    default:
      return null;
  }
};

/**
 * A whole-conversation check as its conversation's page says it, where the conversation goes without saying:
 * 'No reply should mention "Amazon".', 'At least one reply should mention "tracking link".'
 */
export const conversationSentence = (check: ScenarioCheck): string => {
  const reply = clause(check, "should");
  const everywhere = EVERY_TURN_KINDS.has(check.kind) || check.when === "every_turn";
  const never = check.expect === "should_not";
  let sentence: string;
  if (reply.startsWith("the reply ")) {
    const rest = reply.slice("the reply ".length);
    sentence = never ? `no reply ${rest}` : everywhere ? `every reply ${rest}` : `at least one reply ${rest}`;
  } else if (never) {
    sentence = clause(check, "should never");
  } else if (everywhere) {
    sentence = `on every turn, ${reply}`;
  } else if (check.kind === "only_tools" || check.kind === "reply_meets" || counts(check)) {
    // Said of the whole conversation at once, so "at least once" would be wrong.
    sentence = reply;
  } else {
    sentence = `at least once, ${reply}`;
  }
  if (isScored(check) && check.pass_score != null && check.pass_score !== PASS_SCORE) {
    sentence += ` (passes at ${Number(check.pass_score.toPrecision(6))})`;
  }
  return asSentence(sentence);
};

// ---- what blocks saving, and what has gone stale ----

const countProblem = (check: ScenarioCheck): string | null => {
  const low = check.min_calls ?? null;
  const high = check.max_calls ?? null;
  if ([low, high].some((count) => count != null && (!Number.isInteger(count) || count < 0))) {
    return "Counts are whole numbers from 0.";
  }
  if (check.kind === "tool_called" && high === 0) return "At most 0 calls can never pass. Use Should not instead.";
  return low != null && high != null && low > high ? "The fewest calls cannot be more than the most." : null;
};

/** Why the check cannot be saved yet, or null when it is complete. */
export const checkMissing = (check: ScenarioCheck): string | null => {
  if (!isPlaced(check)) return check.level === "turn" ? "Pick the turn." : "Choose the conversations.";
  // Settings the check no longer uses are dropped on save, so they cannot hold it up.
  if (check.context === "run_value" && keeps(check, "context") && !filled(check.context_path)) {
    return "Enter where the value is.";
  }
  if (isScored(check) && check.pass_score != null && (check.pass_score < 0 || check.pass_score > 1)) {
    return "A pass score is from 0 to 1.";
  }
  switch (check.kind) {
    case "reply_mentions":
      return filled(check.text) ? null : "Enter the words to look for.";
    case "reply_meets":
      return filled(check.rubric) ? null : "Write the rule.";
    case "reply_matches":
      return check.match ? null : "Pick how closely it should match.";
    case "reply_grounded":
    case "step_fails":
      return null;
    case "tool_called":
      if (!toolRefs(check).every((ref) => filled(ref.tool) || filled(ref.tool_name)))
        return toolRefs(check).length > 1 ? "Pick each tool." : "Pick the tool.";
      return check.expect === "should" ? countProblem(check) : null;
    case "only_tools":
      if (!(check.tools ?? []).every((ref) => filled(ref.tool) || filled(ref.tool_name))) return "Pick each tool.";
      if (check.expect === "should_not") return check.tools?.length ? null : "Pick the tools it should not use.";
      return countProblem(check);
    case "step_runs":
      return filled(check.step) || filled(check.step_name) || filled(check.step_type) ? null : "Pick the step.";
    case "route_taken":
      return filled(check.branch) || filled(check.branch_label) ? null : "Pick the branch.";
    case "value_equals":
      return filled(check.path) ? null : "Enter where the value is.";
    default:
      if (!filled(check.key)) return "Pick or type the value's name.";
      return filled(check.value) ? null : "Enter the value it should have.";
  }
};

/** The turn a turn-level check points at, found the way the run finds it. */
export const findCheckTurn = (
  check: ScenarioCheck,
  conversations: CheckConversation[],
): { conversation: CheckConversation; turn: CheckTurn } | { problem: string } => {
  for (const conversation of conversations) {
    const turn = conversation.turns.find((item) => item.caseId === check.case_id);
    if (turn) return { conversation, turn };
  }
  const conversation = conversations.find((item) => item.key === check.conversation_id);
  const turn = conversation?.turns.find((item) => item.turnIndex === check.turn_index);
  if (conversation && turn && check.turn_index != null) {
    if (check.turn_message && fingerprint(turn.message) !== fingerprint(check.turn_message)) {
      return { problem: "This turn changed since the check was written." };
    }
    return { conversation, turn };
  }
  return { problem: "This turn is no longer in the dataset." };
};

const fingerprint = (message: string): string =>
  message.toLowerCase().split(/\s+/).filter(Boolean).join(" ").slice(0, 120);

const sameName = (first: unknown, second: unknown): boolean => text(first).toLowerCase() === text(second).toLowerCase();

const inCatalog = <T extends { id: string }>(entries: T[], id: unknown, name: unknown, fields: (keyof T)[]): boolean =>
  entries.some(
    (entry) =>
      (filled(id) && entry.id === id) || (filled(name) && fields.some((field) => sameName(entry[field], name))),
  );

// What a check cannot grade at all, said with what that means.
const UNGRADED = "It will not be graded until you fix it.";

/** What has gone stale since the check was written, and what that does to it. */
export const checkProblem = (
  check: ScenarioCheck,
  conversations: CheckConversation[],
  catalog?: EvaluationToolCatalog | null,
): string | null => {
  if (check.level === "conversation") {
    const chosen = chosenConversations(check);
    if (chosen.length && goneConversations(check, conversations) === chosen.length) {
      return chosen.length === 1
        ? `This conversation is no longer in the dataset. ${UNGRADED}`
        : `These conversations are no longer in the dataset. ${UNGRADED}`;
    }
  }
  if (check.level === "turn") {
    const found = findCheckTurn(check, conversations);
    if ("problem" in found) return `${found.problem} ${UNGRADED}`;
  }
  if (!catalog) return null;
  // What the workflow lacks cannot happen, so the check is graded on that, as the older rules were.
  if (check.kind === "tool_called" || check.kind === "only_tools") {
    if (
      (filled(check.agent) || filled(check.agent_name)) &&
      !inCatalog(catalog.agents, check.agent, check.agent_name, ["label"])
    ) {
      return `The agent "${text(check.agent_name || check.agent)}" is not in this workflow. ${UNGRADED}`;
    }
    const tools = catalog.agents.flatMap((agent) => agent.tools);
    const missing = toolRefs(check).find((ref) => !inCatalog(tools, ref.tool, ref.tool_name, ["name", "label"]));
    if (missing)
      return `The tool "${text(missing.tool_name || missing.tool)}" is not in this workflow, so it can never be called.`;
  }
  if (check.kind === "step_runs") {
    if (isStepType(check)) {
      if (!catalog.action_nodes.some((node) => node.type === check.step_type)) {
        return `No step of type "${text(check.step_name || check.step_type)}" is in this workflow, so none can run.`;
      }
    } else if (!inCatalog(catalog.action_nodes, check.step, check.step_name, ["label"])) {
      return `The step "${stepName(check)}" is not in this workflow, so it can never run.`;
    }
  }
  if (
    check.kind === "route_taken" &&
    (filled(check.router) || filled(check.router_name)) &&
    !inCatalog(catalog.routers, check.router, check.router_name, ["label"])
  ) {
    return `The router "${routerName(check)}" is not in this workflow, so it can never take a branch.`;
  }
  return null;
};

/** Where a check applies, named from the dataset. */
export const checkPlace = (check: ScenarioCheck, conversations: CheckConversation[]): string => {
  if (check.level === "every_conversation") return "All conversations";
  if (check.level === "conversation") {
    const labels = chosenConversations(check).map((key) => {
      const label = conversations.find((item) => item.key === key)?.label;
      return label ? `"${label}"` : "a removed conversation";
    });
    if (labels.length <= 2) return labels.join(" and ");
    return `${labels[0]}, ${labels[1]} and ${labels.length - 2} more`;
  }
  const found = findCheckTurn(check, conversations);
  if ("problem" in found) return "Removed turn";
  return `${found.conversation.label} · ${turnLabel(found.turn.position)}`;
};

// ---- saving and loading ----

const KIND_FIELDS: Record<CheckKind, (keyof ScenarioCheck)[]> = {
  reply_mentions: ["text", "match"],
  reply_matches: ["match", "rubric", "pass_score", "llm_provider_id"],
  reply_meets: ["rubric", "context", "context_path", "pass_score", "llm_provider_id"],
  reply_grounded: [
    "context",
    "context_path",
    "rubric",
    "pass_score",
    "llm_provider_id",
    "grader",
    "nli_model",
    "fail_on_contradiction",
    "embedding",
  ],
  tool_called: [
    "tool",
    "tool_name",
    "agent",
    "agent_name",
    "succeeds",
    "result_not_empty",
    "result_contains",
    "min_calls",
    "max_calls",
  ],
  only_tools: ["agent", "agent_name", "min_calls", "max_calls", "succeeds"],
  step_runs: ["step", "step_name", "step_type"],
  route_taken: ["router", "router_name", "branch", "branch_label"],
  state_equals: ["key", "value"],
  value_equals: ["path", "value"],
  step_fails: [],
};

const LEVEL_FIELDS: Record<CheckLevel, (keyof ScenarioCheck)[]> = {
  every_conversation: [],
  conversation: [],
  turn: ["conversation_id", "case_id", "turn_index", "turn_message"],
};

// Settings that only say more about what should happen with a tool.
const SHOULD_TOOL_FIELDS = new Set<keyof ScenarioCheck>([
  "succeeds",
  "result_not_empty",
  "result_contains",
  "min_calls",
  "max_calls",
]);

const keeps = (check: ScenarioCheck, field: keyof ScenarioCheck): boolean => {
  if (field === "context") return check.kind === "reply_grounded" || isPerTurn(check);
  // A path is only kept with the source it belongs to.
  if (field === "context_path") return check.context === "run_value" && keeps(check, "context");
  if (field === "rubric" && check.kind === "reply_matches") return (check.match ?? "meaning") === "meaning";
  // The NLI model and text similarity read no extra instruction and have no AI grader.
  if (field === "rubric" && check.kind === "reply_grounded") return !check.grader;
  if (field === "pass_score") return isScored(check);
  if (field === "llm_provider_id") return isAiGraded(check);
  if (field === "nli_model" || field === "fail_on_contradiction") return check.grader === "nli";
  if (field === "embedding") return check.grader === "similarity" && Object.values(check.embedding ?? {}).some(filled);
  if (field === "match" && check.kind === "reply_mentions") return check.match === "exact";
  const toolKind = check.kind === "tool_called" || check.kind === "only_tools";
  if (toolKind && check.expect === "should_not" && SHOULD_TOOL_FIELDS.has(field)) return false;
  return true;
};

const toolKey = (ref: CheckToolRef) =>
  filled(ref.tool) ? text(ref.tool) : filled(ref.tool_name) ? `name:${text(ref.tool_name)}` : "";

/** What a tool's own call should have, trimmed as the check's own values are. */
const toolConditions = (ref: CheckToolRef): Record<string, unknown> => {
  const args = Object.fromEntries(
    Object.entries(ref.args ?? {})
      .filter(([key]) => filled(key))
      .map(([key, value]) => [key.trim(), text(value)]),
  );
  return {
    ...(Object.keys(args).length ? { args } : {}),
    ...(ref.result_not_empty ? { result_not_empty: true } : {}),
    // Looked for as typed, spaces included, as Tool Usage looked for it.
    ...(ref.result_contains ? { result_contains: ref.result_contains } : {}),
  };
};

/** Each tool once, the check's own tool included, so a repeat is dropped; with conditions, each keeps its own. */
const toolList = (refs: ScenarioCheck["tools"], own?: CheckToolRef, conditions = false): Record<string, unknown>[] => {
  const seen = new Set(own && toolKey(own) ? [toolKey(own)] : []);
  return (refs ?? [])
    .filter((ref) => {
      const key = toolKey(ref);
      if (!key || seen.has(key)) return false;
      seen.add(key);
      return true;
    })
    .map((ref) => ({
      ...(filled(ref.tool) ? { tool: text(ref.tool) } : {}),
      ...(filled(ref.tool_name) ? { tool_name: text(ref.tool_name) } : {}),
      ...(conditions ? toolConditions(ref) : {}),
    }));
};

/** Only what the check's kind and level use, trimmed, so a changed kind leaves nothing behind. */
export const serializeCheck = (check: ScenarioCheck): Record<string, unknown> => {
  const out: Record<string, unknown> = {
    id: check.id,
    expect: check.expect,
    kind: check.kind,
    level: check.level,
    when: EVERY_TURN_KINDS.has(check.kind) ? "every_turn" : check.level === "turn" ? "anywhere" : check.when,
  };
  if (check.level === "conversation") out.conversation_ids = chosenConversations(check);
  for (const field of [...KIND_FIELDS[check.kind], ...LEVEL_FIELDS[check.level]]) {
    const value = check[field];
    if (value == null || value === "" || value === false || !keeps(check, field)) continue;
    if (field === "embedding") {
      out.embedding = Object.fromEntries(
        Object.entries(check.embedding ?? {})
          .filter(([, setting]) => filled(setting))
          .map(([key, setting]) => [key, setting.trim()]),
      );
      continue;
    }
    // Looked for as typed, spaces included, as Tool Usage looked for it.
    const asTyped = field === "turn_message" || field === "result_contains";
    out[field] = typeof value === "string" && !asTyped ? value.trim() : value;
  }
  if (check.kind === "tool_called") {
    const args = Object.fromEntries(
      Object.entries(check.args ?? {})
        .filter(([key]) => filled(key))
        .map(([key, value]) => [key.trim(), text(value)]),
    );
    if (Object.keys(args).length) out.args = args;
    const others =
      check.expect === "should" ? toolList(check.tools, { tool: check.tool, tool_name: check.tool_name }, true) : [];
    if (others.length) out.tools = others;
  }
  if (check.kind === "only_tools") out.tools = toolList(check.tools);
  return out;
};

export const serializeChecks = (
  checks: ScenarioCheck[],
  providerId?: string,
  olderMethods?: OlderMethods | null,
): Record<string, unknown> => ({
  checks: checks.map(serializeCheck),
  ...(providerId && checks.some(isAiGraded) ? { llm_provider_id: providerId } : {}),
  ...(olderMethods ? { older_methods: olderMethods } : {}),
});

const LEVELS = new Set<string>(CHECK_LEVELS.map((level) => level.value));
const KINDS = new Set<string>(CHECK_KINDS.map((kind) => kind.value));

/** A stored checks config as editable checks; entries that are not checks are dropped. */
export const parseChecks = (
  config: unknown,
): { checks: ScenarioCheck[]; providerId: string; olderMethods: OlderMethods | null } => {
  const raw = (config ?? {}) as { checks?: unknown; llm_provider_id?: unknown; older_methods?: unknown };
  const entries = Array.isArray(raw.checks) ? raw.checks : [];
  const checks = entries
    .filter((entry): entry is Record<string, unknown> => Boolean(entry) && typeof entry === "object")
    .filter((entry) => typeof entry.id === "string" && KINDS.has(String(entry.kind)))
    .map((entry) => {
      const args = entry.args && typeof entry.args === "object" ? (entry.args as Record<string, unknown>) : {};
      const kind = entry.kind as CheckKind;
      const everyTurn = EVERY_TURN_KINDS.has(kind);
      const tools = Array.isArray(entry.tools)
        ? (entry.tools as unknown[])
            .filter((ref): ref is Record<string, unknown> => Boolean(ref) && typeof ref === "object")
            .map((ref) => ({
              tool: (ref.tool as string) ?? null,
              tool_name: (ref.tool_name as string) ?? null,
              ...(ref.args && typeof ref.args === "object"
                ? {
                    args: Object.fromEntries(
                      Object.entries(ref.args as Record<string, unknown>).map(([key, value]) => [key, text(value)]),
                    ),
                  }
                : {}),
              ...(ref.result_not_empty === true ? { result_not_empty: true } : {}),
              ...(typeof ref.result_contains === "string" ? { result_contains: ref.result_contains } : {}),
            }))
        : [];
      const level = LEVELS.has(String(entry.level)) ? (entry.level as CheckLevel) : "every_conversation";
      const ids = Array.isArray(entry.conversation_ids)
        ? (entry.conversation_ids as unknown[]).filter((key): key is string => typeof key === "string")
        : [];
      // One chosen conversation was stored as conversation_id before several could be chosen.
      const single =
        level === "conversation" && typeof entry.conversation_id === "string" ? [entry.conversation_id] : [];
      return {
        ...(entry as unknown as ScenarioCheck),
        expect: entry.expect === "should_not" ? "should_not" : "should",
        level,
        conversation_ids: level === "conversation" ? [...new Set([...ids, ...single])] : null,
        conversation_id: level === "turn" ? ((entry.conversation_id as string | undefined) ?? null) : null,
        when: entry.when === "every_turn" || everyTurn ? "every_turn" : "anywhere",
        args: Object.fromEntries(Object.entries(args).map(([key, value]) => [key, text(value)])),
        tools,
        value: entry.value == null ? entry.value : text(entry.value),
      } as ScenarioCheck;
    });
  const older = raw.older_methods;
  return {
    checks,
    providerId: typeof raw.llm_provider_id === "string" ? raw.llm_provider_id : "",
    olderMethods: older && typeof older === "object" && !Array.isArray(older) ? (older as OlderMethods) : null,
  };
};

/** True while an evaluation runs any older method, including one saved with none. */
export const needsConversion = (techniques: string[] | null | undefined): boolean =>
  !techniques?.length || techniques.some((technique) => technique !== CHECKS_TECHNIQUE);

/** What the conversion could not make into checks, until the evaluation is saved in the editor. */
export const leftOutNote = (olderMethods: OlderMethods | null | undefined, includeReviewed = false): string[] =>
  olderMethods && (includeReviewed || !olderMethods.reviewed) ? (olderMethods.left_out ?? []) : [];
