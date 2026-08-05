import {
  EVALUATION_BUNDLE_KIND,
  BundleRefCandidate,
  EvaluationBundle,
} from "@/interfaces/evalBundle.interface";
import { EvaluationToolCatalog } from "@/interfaces/testEvaluation.interface";

export const bundleFilename = (evaluationName: string): string => {
  const slug = evaluationName
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
  return `evaluation-${slug || "bundle"}.json`;
};

export const downloadJsonFile = (filename: string, data: unknown): void => {
  const blob = new Blob([JSON.stringify(data, null, 2)], {
    type: "application/json",
  });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(url);
};

const dedupeById = (options: BundleRefCandidate[]): BundleRefCandidate[] => {
  const seen = new Set<string>();
  return options.filter((option) => {
    if (seen.has(option.id)) return false;
    seen.add(option.id);
    return true;
  });
};

/** Target-workflow options a manual pick can choose from, per reference kind. */
export const catalogOptionsForKind = (
  catalog: EvaluationToolCatalog | null,
  kind: string,
): BundleRefCandidate[] => {
  if (!catalog) return [];
  if (kind === "tool") {
    return dedupeById(
      catalog.agents.flatMap((agent) =>
        agent.tools.map((tool) => ({ id: tool.id, label: tool.label })),
      ),
    );
  }
  if (kind === "agent") {
    return catalog.agents.map((agent) => ({ id: agent.id, label: agent.label }));
  }
  if (kind === "router") {
    return catalog.routers.map((router) => ({ id: router.id, label: router.label }));
  }
  return catalog.action_nodes.map((node) => ({ id: node.id, label: node.label }));
};

/** Node type per target-workflow node id. Routers are omitted upstream because
 * they are all routerNode, so a type comparison there says nothing. */
export const buildNodeTypeIndex = (
  catalog: EvaluationToolCatalog | null,
): Record<string, string> => {
  const types: Record<string, string> = {};
  if (!catalog) return types;
  for (const agent of catalog.agents) {
    if (agent.type) types[agent.id] = agent.type;
    for (const tool of agent.tools) {
      if (tool.type) types[tool.id] = tool.type;
    }
  }
  for (const node of catalog.action_nodes) {
    if (node.type) types[node.id] = node.type;
  }
  return types;
};

/** Narrow a candidate list to nodes that could play the same role as the
 * original — the ones sharing its node type.
 *
 * Returns null when narrowing says nothing: no recorded type, or every option
 * already matches. An empty array is meaningful and distinct — the workflow has
 * nodes of this kind but none of the right type — so the caller can say so
 * rather than offering an arbitrary pick.
 */
export const narrowToOriginalType = (
  options: BundleRefCandidate[],
  originalType: string | null | undefined,
  typeById: Record<string, string>,
  alwaysKeep: BundleRefCandidate[] = [],
): BundleRefCandidate[] | null => {
  // With no types known (e.g. the catalog failed to load) narrowing would hide
  // every option and claim nothing fits.
  if (!originalType || Object.keys(typeById).length === 0) return null;
  const keepIds = new Set(alwaysKeep.map((option) => option.id));
  const narrowed = options.filter(
    (option) => typeById[option.id] === originalType || keepIds.has(option.id),
  );
  return narrowed.length === options.length ? null : narrowed;
};

/** Key for manual resolution picks: a ref value can appear under two kinds
 * (an agent node id is also an action node), so picks are keyed by both. */
export const nodeRefKey = (nodeRef: { ref: string; kind: string }): string =>
  `${nodeRef.kind}:${nodeRef.ref}`;

export const parseBundleFile = (fileText: string): EvaluationBundle => {
  let parsed: unknown;
  try {
    parsed = JSON.parse(fileText);
  } catch {
    throw new Error("The file is not valid JSON.");
  }
  const bundle = parsed as EvaluationBundle;
  const isBundle =
    bundle &&
    bundle.kind === EVALUATION_BUNDLE_KIND &&
    Boolean(bundle.evaluation?.name) &&
    Boolean(bundle.dataset?.name);
  if (!isBundle) {
    throw new Error("The file is not an evaluation bundle export.");
  }
  // A hand-edited bundle may omit optional collections; normalize them so the
  // dialog never renders against undefined.
  return {
    ...bundle,
    notes: Array.isArray(bundle.notes) ? bundle.notes : [],
    evaluation: {
      ...bundle.evaluation,
      techniques: Array.isArray(bundle.evaluation.techniques)
        ? bundle.evaluation.techniques
        : [],
    },
    dataset: {
      ...bundle.dataset,
      cases: Array.isArray(bundle.dataset.cases) ? bundle.dataset.cases : [],
    },
    references: {
      nodes: bundle.references?.nodes ?? {},
      llm_providers: bundle.references?.llm_providers ?? {},
      cases: bundle.references?.cases ?? {},
    },
  };
};
