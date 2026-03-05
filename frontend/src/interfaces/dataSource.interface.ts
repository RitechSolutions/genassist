import type { ConnectionStatus } from "./connectionStatus.interface";

export interface DataSource {
  id?: string;
  name: string;
  source_type: string;
  connection_data: Record<string, string | number | boolean>;
  connection_status?: ConnectionStatus | null;
  is_active: number;
  oauth_status?: "connected" | "disconnected" | "pending" | "error";
  oauth_email?: string;
}

export interface ConditionalField {
  field: string;
  value: string | number | boolean;
}

export interface DataSourceField {
  name: string;
  label: string;
  type:
    | "text"
    | "number"
    | "password"
    | "select"
    | "boolean"
    | "tags"
    | "files";
  required: boolean;
  default?: string | number | boolean;
  description?: string;
  options?: { value: string; label: string }[];
  placeholder?: string;
  conditional?: ConditionalField;
}

export interface DataSourceConfig {
  name: string;
  fields: DataSourceField[];
}

export interface DataSourcesConfig {
  [key: string]: DataSourceConfig;
}
