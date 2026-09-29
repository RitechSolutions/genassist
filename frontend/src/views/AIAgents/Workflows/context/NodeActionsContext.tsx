import { createContext, useContext } from "react";

/**
 * Actions on a single node that must run at the GraphFlow (canvas) level —
 * they need access to the nodes/edges state, the node registry and the
 * Available Nodes sidebar, none of which a node component owns. GraphFlow
 * provides these; node components consume them via `useNodeActions()`.
 */
export interface NodeActionsContextValue {
  /** Clone a node onto the canvas (offset from the original, without edges). */
  duplicateNode: (id: string) => void;
  /** Copy a node to the internal clipboard (paste with Cmd/Ctrl+V). */
  copyNode: (id: string) => void;
  /** Open the Available Nodes sidebar in "replace" mode for this node. */
  requestReplaceNode: (id: string) => void;
  /**
   * Run the whole workflow in the Executions test panel. Used by the Start
   * (Chat Input) node's inline "Test" affordance — it's the workflow entry
   * point, so testing "directly" from it runs the full graph.
   */
  testWorkflow: () => void;
  /** Open the name dialog for a visual group (see utils/nodeGroups). */
  renameGroup: (groupId: string) => void;
  /** Remove a group container, keeping its nodes where they are on screen. */
  ungroup: (groupId: string) => void;
  /** Set a group's palette colour (a key from nodeTypes/group/groupColors). */
  setGroupColor: (groupId: string, color: string) => void;
  /** Resize a group to hug its nodes. */
  fitGroup: (groupId: string) => void;
  /** Ask how to delete a group (container only, or with its nodes). */
  requestDeleteGroup: (groupId: string) => void;
}

export const NodeActionsContext = createContext<NodeActionsContextValue | null>(
  null
);

/**
 * Read node-level canvas actions. Returns null when a node is rendered outside
 * a provider (e.g. read-only Execution/Diff views) so callers can no-op safely.
 */
export const useNodeActions = () => useContext(NodeActionsContext);
