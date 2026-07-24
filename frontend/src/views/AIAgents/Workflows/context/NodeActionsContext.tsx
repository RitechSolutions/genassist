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
}

export const NodeActionsContext = createContext<NodeActionsContextValue | null>(
  null
);

/**
 * Read node-level canvas actions. Returns null when a node is rendered outside
 * a provider (e.g. read-only Execution/Diff views) so callers can no-op safely.
 */
export const useNodeActions = () => useContext(NodeActionsContext);
