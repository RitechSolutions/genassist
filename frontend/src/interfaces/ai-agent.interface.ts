export interface AIAgentFile {
  id: string;
  name: string;
}

export interface AIAgent {
  id: string;
  name: string;
  provider: string;
  model: string;
  files?: AIAgentFile[];
  filesCount: number;
  systemPrompt?: string;
}

/**
 * Security settings for an agent
 */
export interface AgentSecuritySettings {
  id?: string;
  agent_id?: string;
  token_based_auth?: boolean;
  token_expiration_minutes?: number | null;
  cors_allowed_origins?: string | null;
  rate_limit_conversation_start_per_minute?: number | null;
  rate_limit_conversation_start_per_hour?: number | null;
  rate_limit_conversation_update_per_minute?: number | null;
  rate_limit_conversation_update_per_hour?: number | null;
  recaptcha_enabled?: boolean | null;
  recaptcha_project_id?: string | null;
  recaptcha_site_key?: string | null;
  recaptcha_min_score?: string | null;
  gcp_svc_account?: string | null;
}

/**
 * Full agent configuration returned by detail endpoints
 */
export interface AgentConfig {
  id: string;
  name: string;
  description: string;
  is_active?: boolean;
  welcome_message?: string;
  welcome_title?: string;
  thinking_phrase_delay?: number;
  possible_queries?: string[];
  thinking_phrases?: string[];
  workflow_id: string;
  user_id: string;
  security_settings?: AgentSecuritySettings | null;
  [key: string]: unknown;
}

/**
 * Minimal agent data for list view - optimized for performance
 */
export interface AgentListItem {
  id: string;
  name: string;
  workflow_id: string | null;
  possible_queries: string[];
  is_active: boolean;
}

export type AgentConfigCreate = Omit<AgentConfig, "id" | "user_id" | "workflow_id">;

export type AgentConfigUpdate = Partial<Omit<AgentConfig, "id" | "user_id">>;
