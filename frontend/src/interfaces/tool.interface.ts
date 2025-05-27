export interface ApiConfig {
  url: string;
  method: string;
  headers?: Record<string, string>;
  auth?: {
    type: string;
    config: Record<string, unknown>;
  };
}

export interface FunctionConfig {
  code: string;
  language: string;
  dependencies?: string[];
}

export interface ToolParameter {
  name: string;
  type: string;
  description?: string;
  required?: boolean;
  default?: unknown;
}

export interface Tool {
  id: string;
  name: string;
  description?: string;
  type: "api" | "function" | "browser";
  api_config?: ApiConfig;
  function_config?: FunctionConfig;
  parameters_schema: Record<string, ToolParameter>;
  parameters?: ToolParameter[];
  [key: string]: unknown;
}
