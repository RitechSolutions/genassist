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
  /** A focused AI action on one node (explain, improve prompt, generate, suggest tests). */
  assistNode: (id: string, action: "explain_node" | "improve_prompt" | "generate_code" | "suggest_tests" | "explain_step") => void;
  /** Ask the assistant to fix a problem on one node. */
  fixNodeWithAi: (id: string, problem: string) => void;
  /** A focused AI action on a group's nodes (explain, optimize). */
  assistGroup: (groupId: string, action: "explain_group" | "optimize") => void;
  /**
   * "Add with AI" on an output handle: one new step after that output, designed
   * from a sentence. `handleLabel` is the output's name as the tooltip shows it.
   */
  addStepWithAi: (nodeId: string, handleId: string, handleLabel: string, instruction: string) => void;
}

export const NodeActionsContext = createContext<NodeActionsContextValue | null>(
  null
);

/**
 * Read node-level canvas actions. Returns null when a node is rendered outside
 * a provider (e.g. read-only Execution/Diff views) so callers can no-op safely.
 */
export const useNodeActions = () => useContext(NodeActionsContext);
