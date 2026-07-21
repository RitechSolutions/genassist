export interface TemplateListItem {
  id: string;
  title: string;
  description?: string | null;
  category?: string | null;
  icon?: string | null;
  tags: string[];
  node_types: string[];
  node_count: number;
  install_count: number;
  is_official: boolean;
  is_global: boolean;
  publish_status?: string | null;
  source_tenant?: string | null;
}

export interface TemplateGraph {
  nodes: unknown[];
  edges: unknown[];
  testInput?: unknown;
}

export interface Template extends TemplateListItem {
  graph: TemplateGraph;
  agent_config?: Record<string, unknown> | null;
  created_at?: string | null;
}

export interface InstallTemplateResponse {
  agent_id: string;
  workflow_id: string;
}

export interface CreateTemplateFromAgentPayload {
  agent_id: string;
  title: string;
  description?: string;
  category?: string;
  icon?: string;
  tags?: string[];
}
