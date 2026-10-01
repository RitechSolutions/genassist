import type { Node } from "reactflow";

// Matches a trailing copy counter, e.g. the " (2)" in "Sub-Agent (2)".
const COPY_SUFFIX = /\s*\((\d+)\)$/;

/**
 * Name for a copy of a node: the original name with the first free "(n)" counter, so copying
 * "Sub-Agent" gives "Sub-Agent (1)", then "Sub-Agent (2)". Copying an already-numbered node
 * continues the same series instead of nesting counters ("Sub-Agent (1) (1)").
 */
export const getCopyName = (name: string, takenNames: Iterable<string>): string => {
  const taken = takenNames instanceof Set ? takenNames : new Set(takenNames);
  const base = name.replace(COPY_SUFFIX, "") || name;
  let n = 1;
  while (taken.has(`${base} (${n})`)) n += 1;
  return `${base} (${n})`;
};

const getNodeName = (node: Node): string | undefined => {
  const name = (node.data as { name?: unknown } | undefined)?.name;
  return typeof name === "string" && name.trim() ? name : undefined;
};

/**
 * Renames freshly copied nodes so each gets a unique "(n)" name against the nodes already on the
 * canvas and against each other. Unnamed nodes are left untouched.
 */
export const withCopyNames = (copies: Node[], existing: Node[]): Node[] => {
  const taken = new Set<string>();
  existing.forEach((node) => {
    const name = getNodeName(node);
    if (name) taken.add(name);
  });

  return copies.map((node) => {
    const name = getNodeName(node);
    if (!name) return node;
    const copyName = getCopyName(name, taken);
    taken.add(copyName);
    return { ...node, data: { ...node.data, name: copyName } };
  });
};
