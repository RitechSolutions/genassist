import { Node, Edge } from 'reactflow';


// Workflow interface representing a saved workflow configuration
export interface Workflow {
  id?: string;
  name: string;
  description?: string;
  nodes: Node[];
  edges: Edge[];
  version: string;
  created_at?: string;
  updated_at?: string;
}

// Payload for creating a new workflow
export interface WorkflowCreatePayload {
  name: string;
  description?: string;
  nodes: Node[];
  edges: Edge[];
  version: string;
}

// Payload for updating an existing workflow
export interface WorkflowUpdatePayload {
  name?: string;
  description?: string;
  nodes: Node[];
  edges: Edge[];
  version: string;
} 