import { isEqual } from 'lodash';
import { Edge, Node } from 'reactflow';
import { Workflow } from '@/interfaces/workflow.interface';
import {
  DiffSummary,
  EdgeDiff,
  FieldChange,
  NodeDiff,
  NodeDiffStatus,
  WorkflowDiff,
} from '@/interfaces/workflow-diff.interface';
import nodeRegistry from '../registry/nodeRegistry';

/**
 * Pure diff engine for the Workflow Version Diff Checker (feature 005).
 *
 * Mirrors — and extends — the builder's `compareWorkflows` cosmetic-stripping rules
 * (`GraphFlow.tsx`) so the notion of a "meaningful change" stays consistent with the rest of the
 * app. In addition to the builder's stripped fields it also drops each node's `position`/
 * `positionAbsolute` (a move is cosmetic per spec FR-7) and the runtime-injected
 * `data.updateNodeData` function (not real configuration). Everything here is a deterministic pure
 * function so it is fully unit-testable (see `versionDiff.test.ts`).
 */

type UnknownRecord = Record<string, unknown>;

/** A workflow reduced to just the meaningful graph, cosmetic fields stripped. */
export interface NormalizedWorkflow {
  nodes: Node[];
  edges: Edge[];
}

const asRecord = (value: unknown): UnknownRecord =>
  value && typeof value === 'object' && !Array.isArray(value) ? (value as UnknownRecord) : {};

/**
 * Deep-clones a workflow and strips all non-meaningful/cosmetic fields:
 * - workflow `created_at` / `updated_at`
 * - per node: `selected`, `dragging`, `width`, `height`, `position`, `positionAbsolute`,
 *   and `data.updateNodeData`
 * - per edge: `selected`, `className`
 */
export const normalizeForDiff = (workflow: Workflow): NormalizedWorkflow => {
  const clone = JSON.parse(JSON.stringify(workflow ?? {})) as Workflow;

  const nodes: Node[] = (clone.nodes ?? []).map((node) => {
    const { selected, dragging, width, height, position, positionAbsolute, ...rest } = node as Node & {
      positionAbsolute?: unknown;
    };
    const data = { ...asRecord(rest.data) };
    delete data.updateNodeData;
    return { ...rest, data } as Node;
  });

  const edges: Edge[] = (clone.edges ?? []).map((edge) => {
    const { selected, className, ...rest } = edge as Edge & { className?: string };
    return rest as Edge;
  });

  return { nodes, edges };
};

/**
 * Human-readable identity for a node, resolved in priority order:
 * `data.name` → registry label for its type → its type → its id.
 */
export const getNodeLabel = (node: Node): string => {
  const data = asRecord(node?.data);
  const name = data.name;
  if (typeof name === 'string' && name.trim()) return name;

  const registryLabel = node?.type ? nodeRegistry.getNodeType(node.type)?.label : undefined;
  if (registryLabel && registryLabel.trim()) return registryLabel;

  if (node?.type) return node.type;
  return node?.id ?? '';
};

/**
 * Field-level comparison of two same-id nodes' normalized `data`. Compares every field present in
 * either node via `isEqual`. If the node's `type` itself changed, that is surfaced as a synthetic
 * `type` field change so the user sees the node was re-typed.
 */
export const diffNodeData = (baseNode: Node, targetNode: Node): FieldChange[] => {
  const changes: FieldChange[] = [];

  if (baseNode.type !== targetNode.type) {
    changes.push({ key: 'type', before: baseNode.type, after: targetNode.type });
  }

  const baseData = asRecord(baseNode.data);
  const targetData = asRecord(targetNode.data);
  const keys = Array.from(new Set([...Object.keys(baseData), ...Object.keys(targetData)]));

  for (const key of keys) {
    if (!isEqual(baseData[key], targetData[key])) {
      changes.push({ key, before: baseData[key], after: targetData[key] });
    }
  }

  return changes;
};

/** Identity of a connection: its source/handles/target tuple, falling back to the edge id. */
const edgeIdentity = (edge: Edge): string => {
  const source = edge.source ?? '';
  const target = edge.target ?? '';
  if (source || target) {
    return `${source}::${edge.sourceHandle ?? ''}::${target}::${edge.targetHandle ?? ''}`;
  }
  return `id:${edge.id ?? ''}`;
};

/**
 * Classifies edges into added (present only in target) and removed (present only in base),
 * matched by connection identity. Human-readable source/target labels are resolved from the node
 * labels of whichever version owns the edge.
 */
export const diffEdges = (base: Workflow, target: Workflow): EdgeDiff[] => {
  const baseNorm = normalizeForDiff(base);
  const targetNorm = normalizeForDiff(target);

  const labelFor = (nodes: Node[], nodeId: string): string => {
    const node = nodes.find((n) => n.id === nodeId);
    return node ? getNodeLabel(node) : nodeId;
  };

  const baseByIdentity = new Map<string, Edge>();
  for (const edge of baseNorm.edges) baseByIdentity.set(edgeIdentity(edge), edge);

  const targetByIdentity = new Map<string, Edge>();
  for (const edge of targetNorm.edges) targetByIdentity.set(edgeIdentity(edge), edge);

  const diffs: EdgeDiff[] = [];

  // Added: in target but not base.
  for (const [identity, edge] of targetByIdentity) {
    if (!baseByIdentity.has(identity)) {
      diffs.push({
        id: edge.id ?? identity,
        status: 'added',
        sourceLabel: labelFor(targetNorm.nodes, edge.source),
        targetLabel: labelFor(targetNorm.nodes, edge.target),
      });
    }
  }

  // Removed: in base but not target.
  for (const [identity, edge] of baseByIdentity) {
    if (!targetByIdentity.has(identity)) {
      diffs.push({
        id: edge.id ?? identity,
        status: 'removed',
        sourceLabel: labelFor(baseNorm.nodes, edge.source),
        targetLabel: labelFor(baseNorm.nodes, edge.target),
      });
    }
  }

  return diffs;
};

/**
 * Computes the full comparison of two workflow versions. Nodes are paired by stable `id`:
 * present only in target ⇒ `added`, only in base ⇒ `removed`, in both with meaningful field
 * changes ⇒ `modified`, in both with none ⇒ `unchanged`. The returned `base`/`target` are the
 * original (un-normalized) workflows so callers can display their name/version/timestamps.
 */
export const computeWorkflowDiff = (base: Workflow, target: Workflow): WorkflowDiff => {
  const baseNorm = normalizeForDiff(base);
  const targetNorm = normalizeForDiff(target);

  const baseById = new Map<string, Node>();
  for (const node of baseNorm.nodes) baseById.set(node.id, node);

  const targetById = new Map<string, Node>();
  for (const node of targetNorm.nodes) targetById.set(node.id, node);

  const nodes: NodeDiff[] = [];
  const summary: DiffSummary = { added: 0, removed: 0, modified: 0, unchanged: 0 };

  const pushNode = (node: Node, status: NodeDiffStatus, fieldChanges: FieldChange[]) => {
    nodes.push({
      id: node.id,
      label: getNodeLabel(node),
      type: node.type ?? '',
      status,
      fieldChanges,
    });
    summary[status] += 1;
  };

  // Iterate target order first (added / modified / unchanged) for a deterministic layout.
  for (const targetNode of targetNorm.nodes) {
    const baseNode = baseById.get(targetNode.id);
    if (!baseNode) {
      pushNode(targetNode, 'added', []);
      continue;
    }
    const fieldChanges = diffNodeData(baseNode, targetNode);
    pushNode(targetNode, fieldChanges.length ? 'modified' : 'unchanged', fieldChanges);
  }

  // Then base-only nodes (removed), in base order.
  for (const baseNode of baseNorm.nodes) {
    if (!targetById.has(baseNode.id)) {
      pushNode(baseNode, 'removed', []);
    }
  }

  const edges = diffEdges(base, target);

  return { base, target, nodes, edges, summary };
};
