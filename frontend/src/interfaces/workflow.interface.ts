import { Node, Edge } from "reactflow";
import { WorkflowExecutionState } from "@/views/AIAgents/Workflows/context/WorkflowExecutionContext";

// Workflow interface representing a saved workflow configuration
export interface Workflow {
  id?: string;
  name: string;
  description?: string;
  nodes?: Node[];
  edges?: Edge[];
  testInput?: Record<string, string>;
  version: string;
  agent_id?: string;
  created_at?: string;
  updated_at?: string;
  // Execution state that gets persisted
  executionState?: WorkflowExecutionState;
}

// Payload for creating a new workflow
export interface WorkflowCreatePayload {
  name: string;
  description?: string;
  nodes: Node[];
  edges: Edge[];
  testInput?: Record<string, string>;
  version: string;
  agent_id: string;
  executionState?: WorkflowExecutionState;
}

// Payload for updating an existing workflow
export interface WorkflowUpdatePayload {
  name?: string;
  description?: string;
  nodes?: Node[];
  edges?: Edge[];  
  testInput?: Record<string, string>;
  version?: string;
  executionState?: WorkflowExecutionState;
}
