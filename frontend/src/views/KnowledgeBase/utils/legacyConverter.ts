import { RagConfigValues } from "../types/ragSchema";

// Default RAG configuration
export const DEFAULT_RAG_CONFIG: RagConfigValues = {
  vector: {
    enabled: false,
    type: "chroma",
    collection_name: "",
  },
  lightrag: {
    enabled: false,
    search_mode: "mix",
  },
  legra: {
    enabled: false,
    questions: "",
  },
};

// Legacy interface for backward compatibility (now same as RagConfigValues)
export interface LegacyRagConfig {
  enabled: boolean;
  vector?: {
    enabled: boolean;
    type: string;
    collection_name: string;
    [key: string]: unknown;
  };
  lightrag?: {
    enabled: boolean;
    search_mode: string;
    [key: string]: unknown;
  };
  legra?: {
    enabled: boolean;
    questions: string;
    [key: string]: unknown;
  };
  [key: string]: unknown;
}

export const DEFAULT_LEGACY_RAG_CONFIG: LegacyRagConfig = {
  enabled: false,
  vector: {
    enabled: false,
    type: "chroma",
    collection_name: "",
  },
  lightrag: {
    enabled: false,
    search_mode: "mix",
  },
  legra: {
    enabled: false,
    questions: "",
  },
};
