import { Edge } from "reactflow";
import { NodeHandler } from "../types/nodes";

/**
 * Edges attached to `nodeId` through a handle that existed in `before` but is
 * gone from `after` — e.g. the output of a Switch case that was just removed.
 * Edges on handles the node never declared are left alone, so older workflows
 * with loosely named handles are not pruned by an unrelated update.
 */
export function edgesOnRemovedHandles(
  edges: Edge[],
  nodeId: string,
  before: NodeHandler[] | undefined,
  after: NodeHandler[] | undefined
): Edge[] {
  const remaining = new Set((after ?? []).map((h) => h.id));
  const removed = new Set(
    (before ?? []).map((h) => h.id).filter((handleId) => !remaining.has(handleId))
  );
  if (removed.size === 0) return [];
  return edges.filter(
    (edge) =>
      (edge.source === nodeId && !!edge.sourceHandle && removed.has(edge.sourceHandle)) ||
      (edge.target === nodeId && !!edge.targetHandle && removed.has(edge.targetHandle))
  );
}
