export interface DataSource {
  id?: string;
  name: string;
  source_type: string;
  connection_data: Record<string, string | number | boolean>;
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
  type: "text" | "number" | "password" | "select" | "files";
  required: boolean;
  default?: string | number;
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
