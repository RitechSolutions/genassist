export interface LLMProvider {
    id: string;
    name: string;
    llm_model_provider: string;
    llm_model: string;
    connection_data: Record<string, any>; 
    is_active: number;
    created_at: string;
    updated_at: string;
  }

export interface LLMProviderField {
  name: string;
  type: 'text' | 'password' | 'select' | 'number' | 'tags';
  label: string;
  required: boolean;
  description?: string;
  default?: string | number;
  min?: number;
  max?: number;
  step?: number;
  options?: Array<{
    value: string;
    label: string;
  }>;
}

export interface LLMProviderConfig {
  name: string;
  fields: LLMProviderField[];
}

export interface LLMProvidersConfig {
  [key: string]: LLMProviderConfig;
}