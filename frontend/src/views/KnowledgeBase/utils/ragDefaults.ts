import { RagConfigValues } from "../types/ragSchema";

// Default RAG configuration
export const DEFAULT_RAG_CONFIG: RagConfigValues = {
  vector: {
    enabled: false,
    type: "chroma",
  },
  lightrag: {
    enabled: false,
  },
  legra: {
    enabled: false,
  },
};

// Legacy interface for backward compatibility (now same as RagConfigValues)
export interface LegacyRagConfig {
  enabled: boolean;
  vector?: {
    enabled: boolean;
    type: string;
    [key: string]: unknown;
  };
  lightrag?: {
    enabled: boolean;
    [key: string]: unknown;
  };
  legra?: {
    enabled: boolean;
    [key: string]: unknown;
  };
  [key: string]: unknown;
}

export const DEFAULT_LEGACY_RAG_CONFIG: LegacyRagConfig = {
  enabled: false,
  vector: {
    enabled: false,
    type: "chroma",
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
