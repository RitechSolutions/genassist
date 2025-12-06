import React, { createContext, useContext } from "react";
import { Workflow } from "@/interfaces/workflow.interface";

// Define the context type
export type WorkflowContextType = {
  workflow: Workflow | undefined;
  setWorkflow: React.Dispatch<React.SetStateAction<Workflow | undefined>>;
};

// Create the context
export const WorkflowContext = createContext<WorkflowContextType | undefined>(undefined);

// Custom hook for consuming the context
export const useWorkflow = () => {
  const context = useContext(WorkflowContext);
  if (!context) {
    throw new Error("useWorkflow must be used within a WorkflowProvider");
  }
  return context;
};

// Provider component
export const WorkflowProvider: React.FC<{
  workflow: Workflow | undefined;
  setWorkflow: React.Dispatch<React.SetStateAction<Workflow | undefined>>;
  children: React.ReactNode;
}> = ({ workflow, setWorkflow, children }) => (
  <WorkflowContext.Provider value={{ workflow, setWorkflow }}>
    {children}
  </WorkflowContext.Provider>
); 