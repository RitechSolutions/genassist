import type { ConnectionStatus } from '@/interfaces/connectionStatus.interface';

export interface LLMProvider {
  id: string;
  name: string;
  llm_model_provider: string;
  llm_model: string;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  connection_data: Record<string, any>;
  connection_status?: ConnectionStatus | null;
  is_active: number;
  created_at: string;
  updated_at: string;
  prompt_caching_mode?: "explicit" | "automatic" | "none";
}

export interface LLMProviderMinimal {
  id: string;
  name: string;
  llm_model_provider: string;
  llm_model: string;
  is_active: number;
}
