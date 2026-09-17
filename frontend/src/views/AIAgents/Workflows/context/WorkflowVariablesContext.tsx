import React, { createContext, useContext, useMemo } from "react";
import {
  buildVariableTree,
  VariableNode,
  VariableNodeNames,
} from "@/helpers/variable-input/variableTree";

interface WorkflowVariablesValue {
  tree: VariableNode[];
}

const EMPTY: WorkflowVariablesValue = { tree: [] };

const WorkflowVariablesContext = createContext<WorkflowVariablesValue>(EMPTY);

/**
 * Makes the node's available data reachable from any field rendered inside the
 * config panel, so inputs can offer variables without the dialogs threading
 * props down. Outside the panel the list is empty and the pickers stay hidden.
 */
export const WorkflowVariablesProvider: React.FC<{
  data: unknown;
  nodeNames?: VariableNodeNames;
  children: React.ReactNode;
}> = ({ data, nodeNames, children }) => {
  const value = useMemo(
    () => ({ tree: buildVariableTree(data, nodeNames) }),
    [data, nodeNames]
  );

  return (
    <WorkflowVariablesContext.Provider value={value}>
      {children}
    </WorkflowVariablesContext.Provider>
  );
};

export function useWorkflowVariables(): WorkflowVariablesValue {
  return useContext(WorkflowVariablesContext);
}
