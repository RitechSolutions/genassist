import { Workflow } from '@/interfaces/workflow.interface';

/**
 * View-model types for the Workflow Version Diff Checker (feature 005).
 *
 * A `WorkflowDiff` is the pure, read-only result of comparing two saved versions of the same
 * workflow (`base` = older, `target` = newer). Both the grouped-list and side-by-side graph
 * presentations read from this single model so they can never disagree (spec FR-13, AC-12).
 */

/** How a node changed between the two compared versions. */
export type NodeDiffStatus = 'added' | 'removed' | 'modified' | 'unchanged';

/** A single configuration field that differs between base and target for a modified node. */
export interface FieldChange {
  /** Field key within the node's `data` (or the synthetic `type` key when the node type changed). */
  key: string;
  /** Value in the base (older) version. */
  before: unknown;
  /** Value in the target (newer) version. */
  after: unknown;
}

/** Per-node diff entry: identity, classification and (for modified nodes) its field-level changes. */
export interface NodeDiff {
  /** Stable node id used to pair nodes across versions. */
  id: string;
  /** Human-readable node identity (name / registry label / type / id). */
  label: string;
  /** The node's type (from the target version when present, otherwise the base version). */
  type: string;
  status: NodeDiffStatus;
  /** Field-level old→new changes; only populated for `modified` nodes. */
  fieldChanges: FieldChange[];
}

/** A connection (edge) that was added or removed between the two versions. */
export interface EdgeDiff {
  /** Identity of the edge (its id, or the source/target connection tuple). */
  id: string;
  status: 'added' | 'removed';
  /** Human-readable label of the source node this connection starts from. */
  sourceLabel: string;
  /** Human-readable label of the target node this connection ends at. */
  targetLabel: string;
}

/** Aggregate counts of node classifications for the summary header (spec FR-4). */
export interface DiffSummary {
  added: number;
  removed: number;
  modified: number;
  unchanged: number;
}

/** The complete comparison of two workflow versions. */
export interface WorkflowDiff {
  /** The older version (base). */
  base: Workflow;
  /** The newer version (target). */
  target: Workflow;
  nodes: NodeDiff[];
  edges: EdgeDiff[];
  summary: DiffSummary;
}
