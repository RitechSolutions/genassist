export interface KnowledgeItem {
  id: string;
  name: string;
  description?: string;
  type?: string;
  rag_config?: {
    enabled: boolean;
    graph_db?: {
      enabled: boolean;
      type?: string;
    };
  };
  [key: string]: unknown;
} 