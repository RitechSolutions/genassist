import type { VariableNode } from "@/helpers/variable-input/variableTree";

/**
 * Advisory checks on `{{variable}}` tokens. Engine decides what's valid,
 * so nothing here blocks saving, evaluating, or accepting.
 */

export const readPromptBindings = (text: string): string[] => {
  if (!text) return [];
  const tokens = text.match(/{{[^\s{}]+}}/g) ?? [];
  return [...new Set(tokens.map((token) => token.slice(2, -2)))];
};

export type DiagnosticKind = "unclosed" | "malformed" | "spaced" | "multiline";

export interface VariableDiagnostic {
  kind: DiagnosticKind;
  /** The candidate as written, shortened for display */
  text: string;
  /** Offset of the opening "{{", so two identical typos stay distinct */
  index: number;
}

export interface BraceScan {
  findings: VariableDiagnostic[];
  /** True when the scan stopped at the cap, so the panel can say "and more" */
  truncated: boolean;
}

/** Read after the offending text, so each reads as the rest of a sentence */
export const DIAGNOSTIC_MESSAGES: Record<DiagnosticKind, string> = {
  unclosed: 'was never closed. Add the matching "}}".',
  malformed: "is not a reference the engine can read.",
  spaced: "has spaces inside the braces, so it will not resolve.",
  multiline: "spans two lines; a reference must stay on one.",
};

const MAX_DIAGNOSTICS = 50;
const PREVIEW_LIMIT = 60;

const preview = (candidate: string): string =>
  candidate.length <= PREVIEW_LIMIT
    ? candidate
    : `${candidate.slice(0, PREVIEW_LIMIT)}…`;

/** What ended the candidate: a "}}", another "{{", or the end of the prompt */
type Terminator = "close" | "open" | "eof";

const classify = (
  candidate: string,
  terminator: Terminator,
): DiagnosticKind | null => {
  if (terminator === "eof") return "unclosed";
  if (terminator === "open") return "malformed";
  if (readPromptBindings(candidate).length > 0) return null;
  if (candidate.includes("\n")) return "multiline";
  if (/\s/.test(candidate)) return "spaced";
  return "malformed";
};

/**
 * Finds malformed template tokens by pairing raw delimiters (not `readPromptBindings`,
 * which requires valid patterns). Single linear pass; slicing only for output
 */
export const scanBraceCandidates = (
  text: string,
  maxDiagnostics = MAX_DIAGNOSTICS,
): BraceScan => {
  const findings: VariableDiagnostic[] = [];
  if (!text) return { findings, truncated: false };

  const add = (start: number, end: number, terminator: Terminator) => {
    const candidate = text.slice(start, end);
    const kind = classify(candidate, terminator);
    if (kind) findings.push({ kind, text: preview(candidate), index: start });
  };

  const delimiters = /\{\{|\}\}/g;
  let open: number | null = null;
  let match: RegExpExecArray | null;

  while ((match = delimiters.exec(text)) !== null) {
    if (findings.length >= maxDiagnostics) return { findings, truncated: true };
    if (match[0] === "{{") {
      // A second "{{" ends the pending candidate: it can no longer close
      if (open !== null) add(open, match.index + 2, "open");
      open = match.index;
      continue;
    }
    // A "}}" with nothing open is ordinary prose, not a broken token
    if (open === null) continue;
    add(open, match.index + 2, "close");
    open = null;
  }

  if (open !== null) {
    if (findings.length >= maxDiagnostics) return { findings, truncated: true };
    add(open, text.length, "eof");
  }
  return { findings, truncated: false };
};

const normalisePath = (path: string): string => path.replace(/\[\d+\]/g, "[]");

const rootOf = (binding: string): string => binding.split(/[.[]/)[0];

/**
 * Bindings the node doesn't offer. Soft warnings: unknown roots aren't reported
 * (runtime resolves arbitrary state), and empty subtrees have no schema to validate
 */
export const unknownBindings = (
  bindings: readonly string[],
  tree: readonly VariableNode[],
): string[] => {
  if (tree.length === 0) return [];

  const known = new Set<string>();
  const collect = (nodes: readonly VariableNode[]) => {
    nodes.forEach((node) => {
      known.add(normalisePath(node.path));
      collect(node.children);
    });
  };
  collect(tree);

  const explored = new Set(
    tree.filter((node) => node.children.length > 0).map((node) => node.path),
  );

  return bindings.filter(
    (binding) =>
      explored.has(rootOf(binding)) && !known.has(normalisePath(binding)),
  );
};

export const unknownDataNote = (unknown: readonly string[]): string | null =>
  unknown.length === 0
    ? null
    : `Not in this node's available data: ${unknown
        .map((binding) => `{{${binding}}}`)
        .join(", ")}. It may still resolve at run time.`;

interface WorkflowEdgeRef {
  source: string;
  target: string;
  targetHandle?: string | null;
}

const EXECUTION_INPUT_HANDLE = "input";

/** Execution input only builds `source`. Matches engine's `base_node.get_input_from_source`
 *  filter; legacy handles like "input_prompt" excluded everywhere */
export const directPredecessorIds = (
  nodeId: string,
  edges: readonly WorkflowEdgeRef[],
): string[] =>
  edges
    .filter(
      (edge) =>
        edge.target === nodeId && edge.targetHandle === EXECUTION_INPUT_HANDLE,
    )
    .map((edge) => edge.source);

export const fanInNote = (
  bindings: readonly string[],
  predecessorIds: readonly string[],
): string | null => {
  if (predecessorIds.length < 2) return null;

  const ids = new Set(predecessorIds);
  const bare = bindings.some((binding) => {
    const [root, second] = binding.split(".");
    return root === "source" && second !== undefined && !ids.has(second);
  });
  if (!bare) return null;

  return (
    `This node has ${predecessorIds.length} direct predecessors, so ` +
    "{{source.…}} is keyed by node id, use {{source.<node id>.field}}."
  );
};

export interface BindingChanges {
  removed: string[];
  added: string[];
  /** Broken tokens the suggestion introduces, not ones it carried over */
  broken: VariableDiagnostic[];
}

export const comparePromptBindings = (
  current: string,
  suggested: string,
): BindingChanges => {
  const before = readPromptBindings(current);
  const after = readPromptBindings(suggested);
  const beforeSet = new Set(before);
  const afterSet = new Set(after);
  const carried = new Set(
    scanBraceCandidates(current).findings.map((finding) => finding.text),
  );

  return {
    removed: before.filter((binding) => !afterSet.has(binding)),
    added: after.filter((binding) => !beforeSet.has(binding)),
    broken: scanBraceCandidates(suggested).findings.filter(
      (finding) => !carried.has(finding.text),
    ),
  };
};

/** One line for the Accept banner. Null when the suggestion keeps every
 *  placeholder intact, which is the normal case */
export const bindingChangeNote = (changes: BindingChanges): string | null => {
  const listed = (bindings: readonly string[]) =>
    bindings.map((binding) => `{{${binding}}}`).join(", ");

  const parts: string[] = [];
  if (changes.removed.length > 0) parts.push(`drops ${listed(changes.removed)}`);
  if (changes.added.length > 0) parts.push(`adds ${listed(changes.added)}`);
  if (changes.broken.length > 0)
    parts.push(
      `introduces ${changes.broken.length} broken ${
        changes.broken.length === 1 ? "token" : "tokens"
      }`,
    );

  return parts.length === 0 ? null : `The suggestion ${parts.join(", ")}.`;
};
