export interface DashboardSummaryStats {
  active_agents: number;
  workflow_runs: number;
  avg_response_time_ms: number;
}

export interface ActiveConversationItem {
  id: string;
  topic: string | null;
  feedback: string | null; // "Good", "Bad", "Neutral"
  duration: number;
  last_message: string | null;
  status: string;
  created_at: string;
  negative_reason: string | null;
  in_progress_hostility_score: number;
}

export interface ActiveConversationsResponse {
  total: number;
  good_count: number;
  neutral_count: number;
  bad_count: number;
  conversations: ActiveConversationItem[];
  page: number;
  page_size: number;
  has_more: boolean;
}

export interface AgentStatsItem {
  id: string;
  name: string;
  conversations_today: number;
  resolution_rate: number;
  avg_response_time_ms: number;
  cost: number;
  is_active: boolean;
}

export interface AgentStatsResponse {
  agents: AgentStatsItem[];
}

export interface IntegrationItem {
  id: string;
  name: string;
  type: string;
  description: string | null;
  is_active: boolean;
}

export interface IntegrationsResponse {
  integrations: IntegrationItem[];
}

export interface DashboardResponse {
  summary: DashboardSummaryStats;
  active_conversations: ActiveConversationsResponse;
  agents: AgentStatsResponse;
  integrations: IntegrationsResponse;
}
