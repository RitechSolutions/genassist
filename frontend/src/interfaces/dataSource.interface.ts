export interface DataSource {
  id?: string;
  name: string;
  source_type: string;
  connection_data: Record<string, string | number>;
  is_active: number;
}

export interface DataSourceField {
  name: string;
  label: string;
  type: "text" | "number" | "password";
  required: boolean;
  default?: string | number;
  description?: string;
  options?: { value: string; label: string }[];
}

export interface DataSourceConfig {
  name: string;
  fields: DataSourceField[];
}

export interface DataSourcesConfig {
  [key: string]: DataSourceConfig;
}
