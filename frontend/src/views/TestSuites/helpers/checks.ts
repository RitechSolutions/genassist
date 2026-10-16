import type { TestCase } from "@/interfaces/testSuite.interface";
import type {
  CheckKind,
  CheckLevel,
  EvaluationToolCatalog,
  ScenarioCheck,
} from "@/interfaces/testEvaluation.interface";
import {
  conversationLabels,
  groupCasesByConversation,
  turnLabel,
} from "./datasetConversations";

export const CHECKS_TECHNIQUE = "checks";

export const CHECK_KINDS: { value: CheckKind; label: string; description: string }[] = [
  { value: "reply_mentions", label: "The reply mentions", description: "Words or a phrase in the agent's reply." },
  { value: "reply_meets", label: "The reply follows a rule", description: "A rule in plain words, graded by AI." },
  { value: "tool_called", label: "A tool is used", description: "An agent calls a tool, with given values if you want." },
  { value: "step_runs", label: "A step runs", description: "A step of the workflow runs to the end." },
  { value: "route_taken", label: "A router takes a branch", description: "A router or switch picks a branch." },
  { value: "state_equals", label: "A remembered value", description: "A value the workflow keeps between turns." },
];

export const CHECK_LEVELS: { value: CheckLevel; label: string }[] = [
  { value: "every_conversation", label: "Every conversation" },
  { value: "conversation", label: "One conversation" },
  { value: "turn", label: "One turn" },
];

// ---- the dataset as checks see it ----

export interface CheckTurn {
  caseId: string;
  turnIndex: number | null;
  /** 1-based position among the conversation's current turns. */
  position: number;
  message: string;
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
      })),
    }));
};

// ---- new checks ----

export interface CheckTarget {
  level: CheckLevel;
  conversation?: CheckConversation;
  turn?: CheckTurn;
}

const randomId = (): string =>
  globalThis.crypto?.randomUUID?.() ?? `${Date.now().toString(36)}${Math.random().toString(36).slice(2)}`;

/** The fields that point a check at its conversation or turn. */
export const targetFields = (target: CheckTarget): Partial<ScenarioCheck> => ({
  level: target.level,
  conversation_id: target.level === "every_conversation" ? null : target.conversation?.key ?? null,
  case_id: target.level === "turn" ? target.turn?.caseId ?? null : null,
  turn_index: target.level === "turn" ? target.turn?.turnIndex ?? null : null,
  turn_message: target.level === "turn" ? target.turn?.message ?? null : null,
});

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

const filled = (value: unknown): boolean => String(value ?? "").trim().length > 0;
const text = (value: unknown): string => String(value ?? "").trim();

export const toolName = (check: ScenarioCheck): string => text(check.tool_name || check.tool);
export const stepName = (check: ScenarioCheck): string => text(check.step_name || check.step);
export const routerName = (check: ScenarioCheck): string => text(check.router_name || check.router);
export const branchName = (check: ScenarioCheck): string => text(check.branch_label || check.branch);

const isPerTurn = (check: ScenarioCheck): boolean =>
  check.level === "turn" || (check.level === "every_conversation" && check.when === "every_turn");

const argPairs = (args: Record<string, string> | undefined): string =>
  Object.entries(args ?? {})
    .filter(([key]) => filled(key))
    .map(([key, value]) => `${key.trim()} = ${text(value)}`)
    .join(", ");

const clause = (check: ScenarioCheck, modal: string): string => {
  switch (check.kind) {
    case "reply_mentions":
      return `the reply ${modal} mention "${text(check.text)}"`;
    case "reply_meets":
      return `${isPerTurn(check) ? "the reply" : "the agent"} ${modal} do this: "${text(check.rubric)}"`;
    case "tool_called": {
      let result = `the tool "${toolName(check)}" ${modal} be called`;
      if (filled(check.agent_name) || filled(check.agent)) result += ` by "${text(check.agent_name || check.agent)}"`;
      const pairs = argPairs(check.args);
      if (pairs) result += ` with ${pairs}`;
      return result;
    }
    case "step_runs":
      return `the step "${stepName(check)}" ${modal} run`;
    case "route_taken":
      return `the router "${routerName(check)}" ${modal} take "${branchName(check)}"`;
    default:
      return `the remembered value "${text(check.key)}" ${modal} be "${text(check.value)}"`;
  }
};

/** A check read back as one sentence, e.g. 'The reply should never mention "RingGo".' */
export const checkSentence = (check: ScenarioCheck): string => {
  const once =
    check.level === "conversation" || (check.level === "every_conversation" && check.when !== "every_turn");
  const modal = check.expect === "should_not" ? (once ? "should never" : "should not") : "should";
  let prefix = "";
  if (check.level === "every_conversation") {
    if (check.when === "every_turn") prefix = "On every turn, ";
    else prefix = check.expect === "should" ? "In every conversation, at some point, " : "In every conversation, ";
  } else if (check.level === "conversation" && check.expect === "should") {
    prefix = "At some point, ";
  }
  const sentence = prefix + clause(check, modal);
  return `${sentence.charAt(0).toUpperCase()}${sentence.slice(1)}.`;
};

// ---- what blocks saving, and what has gone stale ----

/** Why the check cannot be saved yet, or null when it is complete. */
export const checkMissing = (check: ScenarioCheck): string | null => {
  if (check.level === "conversation" && !check.conversation_id) return "Pick the conversation.";
  if (check.level === "turn" && !check.case_id && !(check.conversation_id && check.turn_index != null)) {
    return "Pick the turn.";
  }
  switch (check.kind) {
    case "reply_mentions":
      return filled(check.text) ? null : "Enter the words to look for.";
    case "reply_meets":
      return filled(check.rubric) ? null : "Write the rule.";
    case "tool_called":
      return filled(check.tool) || filled(check.tool_name) ? null : "Pick the tool.";
    case "step_runs":
      return filled(check.step) || filled(check.step_name) ? null : "Pick the step.";
    case "route_taken":
      if (!filled(check.router) && !filled(check.router_name)) return "Pick the router.";
      return filled(check.branch) || filled(check.branch_label) ? null : "Pick the branch.";
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

const fingerprint = (message: string): string => message.toLowerCase().split(/\s+/).filter(Boolean).join(" ").slice(0, 120);

const sameName = (first: unknown, second: unknown): boolean => text(first).toLowerCase() === text(second).toLowerCase();

const inCatalog = <T extends { id: string }>(entries: T[], id: unknown, name: unknown, fields: (keyof T)[]): boolean =>
  entries.some(
    (entry) =>
      (filled(id) && entry.id === id) ||
      (filled(name) && fields.some((field) => sameName(entry[field], name))),
  );

/** What has gone stale since the check was written: its turn, conversation, tool, step or router. */
export const checkProblem = (
  check: ScenarioCheck,
  conversations: CheckConversation[],
  catalog?: EvaluationToolCatalog | null,
): string | null => {
  if (check.level === "conversation" && !conversations.some((item) => item.key === check.conversation_id)) {
    return "This conversation is no longer in the dataset.";
  }
  if (check.level === "turn") {
    const found = findCheckTurn(check, conversations);
    if ("problem" in found) return found.problem;
  }
  if (!catalog) return null;
  if (check.kind === "tool_called") {
    const tools = catalog.agents.flatMap((agent) => agent.tools);
    if (!inCatalog(tools, check.tool, check.tool_name, ["name", "label"])) {
      return `The tool "${toolName(check)}" is not in this workflow.`;
    }
    if ((filled(check.agent) || filled(check.agent_name)) && !inCatalog(catalog.agents, check.agent, check.agent_name, ["label"])) {
      return `The agent "${text(check.agent_name || check.agent)}" is not in this workflow.`;
    }
  }
  if (check.kind === "step_runs" && !inCatalog(catalog.action_nodes, check.step, check.step_name, ["label"])) {
    return `The step "${stepName(check)}" is not in this workflow.`;
  }
  if (check.kind === "route_taken" && !inCatalog(catalog.routers, check.router, check.router_name, ["label"])) {
    return `The router "${routerName(check)}" is not in this workflow.`;
  }
  return null;
};

/** Where a check applies, named from the dataset. */
export const checkPlace = (check: ScenarioCheck, conversations: CheckConversation[]): string => {
  if (check.level === "every_conversation") return "Every conversation";
  if (check.level === "conversation") {
    return conversations.find((item) => item.key === check.conversation_id)?.label ?? "Removed conversation";
  }
  const found = findCheckTurn(check, conversations);
  if ("problem" in found) return "Removed turn";
  return `${found.conversation.label} · ${turnLabel(found.turn.position)}`;
};

// ---- saving and loading ----

const KIND_FIELDS: Record<CheckKind, (keyof ScenarioCheck)[]> = {
  reply_mentions: ["text"],
  reply_meets: ["rubric"],
  tool_called: ["tool", "tool_name", "agent", "agent_name"],
  step_runs: ["step", "step_name"],
  route_taken: ["router", "router_name", "branch", "branch_label"],
  state_equals: ["key", "value"],
};

const LEVEL_FIELDS: Record<CheckLevel, (keyof ScenarioCheck)[]> = {
  every_conversation: [],
  conversation: ["conversation_id"],
  turn: ["conversation_id", "case_id", "turn_index", "turn_message"],
};

/** Only what the check's kind and level use, trimmed, so a changed kind leaves nothing behind. */
export const serializeCheck = (check: ScenarioCheck): Record<string, unknown> => {
  const out: Record<string, unknown> = {
    id: check.id,
    expect: check.expect,
    kind: check.kind,
    level: check.level,
    when: check.level === "every_conversation" ? check.when : "anywhere",
  };
  for (const field of [...KIND_FIELDS[check.kind], ...LEVEL_FIELDS[check.level]]) {
    const value = check[field];
    if (value == null || value === "") continue;
    out[field] = typeof value === "string" && field !== "turn_message" ? value.trim() : value;
  }
  if (check.kind === "tool_called") {
    const args = Object.fromEntries(
      Object.entries(check.args ?? {})
        .filter(([key]) => filled(key))
        .map(([key, value]) => [key.trim(), text(value)]),
    );
    if (Object.keys(args).length) out.args = args;
  }
  return out;
};

export const serializeChecks = (
  checks: ScenarioCheck[],
  providerId?: string,
): Record<string, unknown> => ({
  checks: checks.map(serializeCheck),
  ...(providerId && checks.some((check) => check.kind === "reply_meets") ? { llm_provider_id: providerId } : {}),
});

const LEVELS = new Set<string>(CHECK_LEVELS.map((level) => level.value));
const KINDS = new Set<string>(CHECK_KINDS.map((kind) => kind.value));

/** A stored checks config as editable checks; entries that are not checks are dropped. */
export const parseChecks = (config: unknown): { checks: ScenarioCheck[]; providerId: string } => {
  const raw = (config ?? {}) as { checks?: unknown; llm_provider_id?: unknown };
  const entries = Array.isArray(raw.checks) ? raw.checks : [];
  const checks = entries
    .filter((entry): entry is Record<string, unknown> => Boolean(entry) && typeof entry === "object")
    .filter((entry) => typeof entry.id === "string" && KINDS.has(String(entry.kind)))
    .map((entry) => {
      const args = entry.args && typeof entry.args === "object" ? (entry.args as Record<string, unknown>) : {};
      return {
        ...(entry as unknown as ScenarioCheck),
        expect: entry.expect === "should_not" ? "should_not" : "should",
        level: LEVELS.has(String(entry.level)) ? (entry.level as CheckLevel) : "every_conversation",
        when: entry.when === "every_turn" ? "every_turn" : "anywhere",
        args: Object.fromEntries(Object.entries(args).map(([key, value]) => [key, text(value)])),
        value: entry.value == null ? entry.value : text(entry.value),
      } as ScenarioCheck;
    });
  return { checks, providerId: typeof raw.llm_provider_id === "string" ? raw.llm_provider_id : "" };
};

/** How many checks sit on each conversation (by key) and each turn (by case id), found in one pass. */
export const checkCounts = (
  checks: ScenarioCheck[],
  conversations: CheckConversation[],
): { byConversation: Map<string, number>; byTurn: Map<string, number> } => {
  const byConversation = new Map<string, number>();
  const byTurn = new Map<string, number>();
  const add = (counts: Map<string, number>, key: string) => counts.set(key, (counts.get(key) ?? 0) + 1);
  for (const check of checks) {
    if (check.level === "conversation" && check.conversation_id) {
      add(byConversation, check.conversation_id);
    } else if (check.level === "turn") {
      const found = findCheckTurn(check, conversations);
      if (!("problem" in found)) add(byTurn, found.turn.caseId);
    }
  }
  return { byConversation, byTurn };
};
