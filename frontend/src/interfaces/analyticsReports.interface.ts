// Mirrors backend Pydantic schemas from backend/app/schemas/analytics.py

export interface AgentDailyStatsItem {
  id: string;
  agent_id: string;
  stat_date: string; // "YYYY-MM-DD"
  execution_count: number;
  success_count: number;
  error_count: number;
  avg_response_ms: number | null;
  min_response_ms: number | null;
  max_response_ms: number | null;
  total_nodes_executed: number;
  avg_success_rate: number | null;
  rag_used_count: number;
  unique_conversations: number;
  finalized_conversations: number;
  in_progress_conversations: number;
  thumbs_up_count: number;
  thumbs_down_count: number;
  last_aggregated_at: string;
}

export interface AgentDailyStatsListResponse {
  items: AgentDailyStatsItem[];
  total: number;
}

export interface AgentStatsSummaryResponse {
  agent_id: string | null;
  from_date: string | null;
  to_date: string | null;
  total_executions: number;
  total_success: number;
  total_errors: number;
  avg_response_ms: number | null;
  avg_success_rate: number | null;
  total_rag_used: number;
  total_unique_conversations: number;
  total_finalized_conversations: number;
  total_in_progress_conversations: number;
  total_thumbs_up: number;
  total_thumbs_down: number;
}

export interface NodeDailyStatsItem {
  id: string;
  agent_id: string;
  node_type: string;
  stat_date: string; // "YYYY-MM-DD"
  execution_count: number;
  success_count: number;
  failure_count: number;
  avg_execution_ms: number | null;
  min_execution_ms: number | null;
  max_execution_ms: number | null;
  total_execution_ms: number | null;
}

export interface NodeDailyStatsListResponse {
  items: NodeDailyStatsItem[];
  total: number;
}

export interface NodeTypeBreakdownItem {
  node_type: string;
  execution_count: number;
  success_count: number;
  failure_count: number;
  unique_conversations: number;
  thumbs_up_count: number;
  thumbs_down_count: number;
  success_rate: number | null;
  avg_execution_ms: number | null;
  total_execution_ms: number | null;
}

export interface NodeTypeBreakdownResponse {
  agent_id: string;
  from_date: string | null;
  to_date: string | null;
  items: NodeTypeBreakdownItem[];
}

export interface AgentStatsSummaryWithComparison {
  current: AgentStatsSummaryResponse;
  previous: AgentStatsSummaryResponse | null;
}

export interface AnalyticsFilterParams {
  agent_id?: string;
  from_date?: string;
  to_date?: string;
  node_type?: string;
}
