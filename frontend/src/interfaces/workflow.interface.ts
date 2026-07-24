import { Node, Edge } from "reactflow";
import { WorkflowExecutionState } from "@/views/AIAgents/Workflows/context/WorkflowExecutionContext";

// How nodes are rendered on the canvas.
// - "detailed": the default full card (header + config rows).
// - "compact":  an n8n-style icon tile with the name below it.
export type WorkflowNodeStyle = "detailed" | "compact";

export const DEFAULT_NODE_STYLE: WorkflowNodeStyle = "detailed";

// Per-workflow editor/UI preferences, persisted with the workflow.
export interface WorkflowSettings {
  nodeStyle?: WorkflowNodeStyle;
}

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
  created_by?: string;
  updated_by?: string;
  // Username of the user who last modified the workflow (resolved by the API)
  updated_by_username?: string;
  // Execution state that gets persisted
  executionState?: WorkflowExecutionState;
  // Per-workflow editor/UI preferences (node rendering style, etc.)
  settings?: WorkflowSettings;
}

// Lightweight workflow data (id, name, version only)
export interface WorkflowMinimal {
  id: string;
  name: string;
  version: string;
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
  settings?: WorkflowSettings;
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
  settings?: WorkflowSettings;
}
