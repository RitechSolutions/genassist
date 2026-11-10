import { Edge, Node } from "reactflow";
import type { StreamEvent } from "genassist-chat-react";
import type {
  AssistProposal,
  BuilderCanvasSnapshot,
  BuilderChange,
  BuilderDraft,
  BuilderIssue,
  BuilderQuestion,
  ReviewFinding,
} from "@/services/workflowBuilder";

/**
 * The canvas assistant works on a server-side draft of the workflow: the canvas
 * is uploaded before each message and the edited draft is read back afterwards.
 * These helpers are the two ends of that round trip.
 */

export interface AssistantMessage {
  id: string;
  speaker: "agent" | "customer";
  text: string;
  /** The steps the person tagged when sending (picked from the "@" list or focused), by id. */
  nodeIds?: string[];
  /** What the assistant changed on the canvas in this reply. */
  changes?: BuilderChange[];
  /** Problems the assistant's changes left behind (never pre-existing ones). */
  issues?: BuilderIssue[];
  /** Changes proposed by a focused action, waiting for the person to apply them. */
  proposals?: AssistProposal[];
  /** Test messages suggested by a focused action; one click runs them. */
  suggestions?: string[];
  /** Findings of a review, each with a fix the builder can be asked for. */
  findings?: ReviewFinding[];
  /** When the reply arrived; replies that just arrived are revealed with a typing animation. */
  arrivedAt?: number;
  /** On the person's message: the assistant changed the canvas in response, so it can be undone. */
  undoable?: boolean;
  /** On the person's message: its changes were undone (or superseded by an earlier undo). */
  undone?: boolean;
  /** What the assistant did before answering: its narrated steps and thoughts, in order. */
  steps?: AssistantStep[];
  /** How long the assistant worked before this reply, in milliseconds. */
  workedMs?: number;
  /** The reply was shown as it streamed in, so it needs no reveal animation. */
  streamed?: boolean;
  /** A question for the person with answers to click (from the builder's ask_user tool). */
  question?: BuilderQuestion;
  /** The answer the person gave to `question`, once they have. */
  answer?: string;
  /** The person's thumbs up or down on this reply. */
  reaction?: "up" | "down";
}

// ── The assistant's work as it happens (streamed turn) ──

/** One narrated step of the assistant's work, or a thought it wrote before acting. */
export interface AssistantStep {
  id: string;
  /** read | lookup | search | edit | test | finalize | question | thought */
  kind: string;
  text: string;
  /** The outcome ("7 of 7 applied"), once the step has ended. */
  detail?: string;
  done: boolean;
}

/** The turn in progress: steps so far and the text the assistant is writing right now. */
export interface LiveTurn {
  startedAt: number;
  steps: AssistantStep[];
  /** Reply text streamed so far (reset when a new model call starts writing). */
  text: string;
  callId: string | null;
}

export const newLiveTurn = (now = Date.now()): LiveTurn => ({ startedAt: now, steps: [], text: "", callId: null });

/**
 * The builder starts each sentence it writes before a tool call with this sign
 * (its prompt asks for it), so the panel can show the text as a thought from the
 * first token instead of guessing. A reply never starts with it.
 */
export const THOUGHT_MARKER = "»";

/** Whether streamed text is a working note rather than the reply. */
export const isThoughtText = (text: string): boolean => text.trimStart().startsWith(THOUGHT_MARKER);

/** The text without its thought marker, for display. */
export const stripThoughtMarker = (text: string): string => {
  const trimmed = text.trimStart();
  return trimmed.startsWith(THOUGHT_MARKER) ? trimmed.slice(THOUGHT_MARKER.length).trimStart() : text;
};

/**
 * Text the model wrote before calling a tool is its reasoning, not the reply:
 * once a step starts, whatever was streamed so far becomes a "thought" step.
 */
function foldTextIntoThought(turn: LiveTurn): LiveTurn {
  const thought = stripThoughtMarker(turn.text).trim();
  if (!thought) return { ...turn, text: "", callId: null };
  return {
    ...turn,
    text: "",
    callId: null,
    steps: [...turn.steps, { id: `thought-${turn.steps.length}`, kind: "thought", text: thought, done: true }],
  };
}

/** Fold one stream frame into the turn. Unknown frames leave it unchanged. */
export function applyLiveStreamEvent(turn: LiveTurn, event: StreamEvent): LiveTurn {
  if (event.type === "delta") {
    const sameCall = turn.callId === event.call_id;
    // A new model call after text was written: the earlier text was a thought.
    const base = sameCall || !turn.text.trim() ? turn : foldTextIntoThought(turn);
    return { ...base, callId: event.call_id, text: (sameCall ? base.text : "") + event.text };
  }
  if (event.type === "step") {
    if (event.phase === "start") {
      const base = foldTextIntoThought(turn);
      const existing = base.steps.findIndex((step) => step.id === event.id);
      const step: AssistantStep = { id: event.id, kind: event.kind, text: event.text, done: false };
      if (existing >= 0) {
        return { ...base, steps: base.steps.map((s, i) => (i === existing ? { ...s, ...step } : s)) };
      }
      return { ...base, steps: [...base.steps, step] };
    }
    return {
      ...turn,
      steps: turn.steps.map((step) =>
        step.id === event.id ? { ...step, done: true, detail: event.detail || undefined } : step
      ),
    };
  }
  return turn;
}

/** What the finished reply keeps from the turn: every step done, the reasoning intact. */
export function settleLiveTurn(turn: LiveTurn, now = Date.now()): Pick<AssistantMessage, "steps" | "workedMs"> {
  const steps = turn.steps.map((step) => (step.done ? step : { ...step, done: true }));
  return { steps: steps.length ? steps : undefined, workedMs: Math.max(0, now - turn.startedAt) };
}

/** A short line for a finished turn: "Worked for 12s · 6 steps · 3 changes". */
export function describeWork(
  steps: AssistantStep[] | undefined,
  workedMs: number | undefined,
  changes?: BuilderChange[]
): string | null {
  const stepCount = steps?.length ?? 0;
  const changeCount = changes?.length ?? 0;
  if (stepCount === 0 && changeCount === 0) return null;
  const parts: string[] = [];
  if (stepCount > 0) {
    const seconds = Math.max(1, Math.round((workedMs ?? 0) / 1000));
    const duration = seconds >= 60 ? `${Math.floor(seconds / 60)}m ${seconds % 60}s` : `${seconds}s`;
    parts.push(`Worked for ${duration}`, `${stepCount} step${stepCount === 1 ? "" : "s"}`);
  }
  if (changeCount > 0) parts.push(`${changeCount} change${changeCount === 1 ? "" : "s"}`);
  return parts.join(" · ");
}

export type ChangeKind = "add" | "update" | "remove";

export const changeKind = (change: BuilderChange): ChangeKind => {
  if (change.op === "add_node" || change.op === "add_tool") return "add";
  if (change.op === "remove_node" || change.op === "disconnect") return "remove";
  return "update";
};

/**
 * Whether a turn changed the shape of the graph (nodes or connections added or
 * removed), as opposed to only editing settings. Only then is the canvas
 * re-arranged: editing a prompt should never move anything.
 */
export const changesAffectLayout = (changes: BuilderChange[]): boolean =>
  changes.some((change) => change.op !== "update_node");

/** Canvas state as plain JSON: callbacks React Flow nodes carry in `data` are dropped. */
export function serializeCanvasForDraft(
  nodes: Node[],
  edges: Edge[],
  selectedNodeId?: string | null,
  lastTestRun?: BuilderCanvasSnapshot["last_test_run"],
  simulateActions = true
): BuilderCanvasSnapshot {
  return JSON.parse(
    JSON.stringify({
      nodes: clearAiChanges(nodes),
      edges,
      selected_node_id: selectedNodeId ?? null,
      last_test_run: lastTestRun ?? null,
      simulate_actions: simulateActions,
    })
  ) as BuilderCanvasSnapshot;
}

/** What to send when the person asks the assistant to finish what it left broken. */
export const FIX_ISSUES_MESSAGE =
  "The workflow still has the problems listed above. Fix them, test it, and finish.";

/**
 * Apply the draft's nodes to the canvas.
 *
 * The draft decides which nodes exist and what their data is. For nodes that
 * were already on the canvas, everything the user controls on the canvas
 * itself (position, size, selection, grouping) is kept from the live node, so
 * the assistant never moves things the user arranged, even if they dragged a
 * node while the assistant was working.
 */
export function mergeDraftNodes(current: Node[], draftNodes: Node[]): Node[] {
  const live = new Map(current.map((node) => [node.id, node]));
  return draftNodes.map((draftNode) => {
    const existing = live.get(draftNode.id);
    if (!existing) return draftNode;
    return { ...existing, type: draftNode.type, data: draftNode.data };
  });
}

/** Issues worth showing under a reply: what this turn introduced and the user can act on. */
export function reportableIssues(draft: BuilderDraft): BuilderIssue[] {
  return draft.issues.filter(
    (issue) => !issue.pre_existing && issue.severity !== "setup"
  );
}

// ── Change preview ──
// Nodes the assistant just added or changed carry `data.aiChange` until the
// person keeps or undoes the turn, so the canvas can highlight them.

export type AiChangeMark = "added" | "changed";

export function markAiChanges(nodes: Node[], changes: BuilderChange[]): Node[] {
  const added = new Set<string>();
  const changed = new Set<string>();
  for (const change of changes) {
    const target = change.op === "add_node" || change.op === "add_tool" ? added : changed;
    change.node_ids.forEach((id) => target.add(id));
  }
  if (added.size === 0 && changed.size === 0) return nodes;
  return nodes.map((node) => {
    const mark: AiChangeMark | undefined = added.has(node.id)
      ? "added"
      : changed.has(node.id)
      ? "changed"
      : undefined;
    if (!mark) return node;
    return { ...node, data: { ...node.data, aiChange: mark } };
  });
}

export function clearAiChanges(nodes: Node[]): Node[] {
  if (!nodes.some((node) => node.data?.aiChange)) return nodes;
  return nodes.map((node) => {
    if (!node.data?.aiChange) return node;
    const { aiChange: _dropped, ...rest } = node.data as Record<string, unknown>;
    return { ...node, data: rest };
  });
}

// ── Slash commands in the chat ──

export interface SlashCommand {
  name: string;
  description: string;
}

export const SLASH_COMMANDS: SlashCommand[] = [
  { name: "explain", description: "Explain the selected step, or the whole workflow" },
  { name: "optimize", description: "Propose structural improvements" },
  { name: "review", description: "Check the workflow for problems" },
  { name: "describe", description: "Describe what this workflow does" },
  { name: "tests", description: "Suggest test messages" },
  { name: "fix", description: "Fix the open problems" },
  { name: "undo", description: "Undo the assistant's last change" },
];

/** Split "/explain the billing step" into the command and the rest. */
export function parseSlashCommand(text: string): { command: string; rest: string } | null {
  const match = /^\/([a-z]+)\b\s*([\s\S]*)$/i.exec(text.trim());
  if (!match) return null;
  const command = match[1].toLowerCase();
  if (!SLASH_COMMANDS.some((c) => c.name === command)) return null;
  return { command, rest: match[2].trim() };
}

/** Node names written as @Name in a message, resolved against the canvas. */
export function mentionedNodeIds(text: string, nodes: Node[]): string[] {
  const names = new Map(
    nodes
      .filter((node) => typeof node.data?.name === "string")
      .map((node) => [String(node.data.name).toLowerCase(), node.id])
  );
  const found: string[] = [];
  for (const [lowerName, id] of names) {
    const pattern = new RegExp(`@${lowerName.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}(?![\\w-])`, "i");
    if (pattern.test(text) && !found.includes(id)) found.push(id);
  }
  return found;
}

export interface MentionableNode {
  id: string;
  name: string;
  type?: string;
}

export type MentionSegment = { text: string } | { node: MentionableNode };

const escapeRegExp = (value: string) => value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

/**
 * Split a message into text and the steps it names, written as @Name or as a
 * quoted "Name" (straight or curly quotes). Longer names win over shorter ones
 * they contain, so "Support Agent" is not read as "Support".
 */
export function splitNodeMentions(text: string, nodes: MentionableNode[], preferIds: string[] = []): MentionSegment[] {
  const named = nodes.filter((node) => node.name.trim().length > 0);
  if (!text || named.length === 0) return [{ text }];
  // Two steps can share a name; the one the person actually picked wins the match, in the
  // order they were picked, and any untagged namesake comes after.
  const rank = (node: MentionableNode) => {
    const index = preferIds.indexOf(node.id);
    return index < 0 ? Number.MAX_SAFE_INTEGER : index;
  };
  const byLength = [...named].sort((a, b) => b.name.length - a.name.length || rank(a) - rank(b));
  const alternation = byLength.map((node) => escapeRegExp(node.name)).join("|");
  const pattern = new RegExp(`@(${alternation})(?![\\w-])|["\u201c](${alternation})["\u201d]`, "gi");
  const segments: MentionSegment[] = [];
  let last = 0;
  for (const match of text.matchAll(pattern)) {
    const name = (match[1] ?? match[2]) as string;
    const node = byLength.find((n) => n.name.toLowerCase() === name.toLowerCase());
    if (!node || match.index === undefined) continue;
    if (match.index > last) segments.push({ text: text.slice(last, match.index) });
    segments.push({ node });
    last = match.index + match[0].length;
  }
  if (last < text.length) segments.push({ text: text.slice(last) });
  return segments.length ? segments : [{ text }];
}
