// Mirrors the backend Pydantic schemas in app/schemas/llm_usage.py

export interface LlmUsageSummaryResponse {
  from_date?: string | null;
  to_date?: string | null;
  total_cost_usd: number;
  cost_is_partial: boolean;
  cost_per_conversation_usd: number | null;
  agent_studio_test_cost_usd: number;
  total_input_tokens: number;
  total_output_tokens: number;
  total_tokens: number;
  total_calls: number;
  configured_calls: number;
  fallback_calls: number;
  legacy_estimate_calls: number;
  unpriced_calls: number;
  priced_token_coverage_pct: number;
}

export interface LlmUsageBreakdownItem {
  id?: string;
  key: string;
  label: string;
  cost_usd: number;
  cost_is_partial: boolean;
  total_tokens: number;
  calls: number;
  unpriced_calls: number;
}

export interface LlmUsageBreakdownResponse {
  dimension: LlmUsageDimension;
  items: LlmUsageBreakdownItem[];
  total: number;
}

export interface LlmUsageTimeseriesItem {
  stat_date: string;
  cost_usd: number;
  total_tokens: number;
  calls: number;
  unpriced_calls: number;
}

export interface LlmUsageTimeseriesResponse {
  items: LlmUsageTimeseriesItem[];
  total: number;
}

export interface LlmUsageAgentOption {
  id: string;
  name: string;
}

export interface LlmUsageFilterOptionsResponse {
  providers: string[];
  models: string[];
  agents: LlmUsageAgentOption[];
}

export type LlmUsageDimension = "provider" | "model" | "agent" | "source";

export interface LlmUsageQueryFilters {
  agent_id?: string;
  group_id?: string;
  from_date?: string;
  to_date?: string;
  provider?: string;
  model?: string;
}
