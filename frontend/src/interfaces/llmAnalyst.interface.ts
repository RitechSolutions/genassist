export interface LLMProvider {
    llm_model: any;
    id: string;
    name: string;
    is_active: number;
    model_name: string;
    connection_data: string;
    llm_type: string;
  }
  
  export interface LLMAnalyst {
    id?: string;
    name: string;
    prompt: string;
    is_active: number;
    llm_provider_id: string;
    llm_provider?: LLMProvider;
    context_enrichments?: string[];
    settings?: Record<string, any>;
  }

  export interface AvailableEnrichment {
    key: string;
    name: string;
    description: string;
  }

  export interface AvailableNodeType {
    node_type: string;
    label: string;
  }

