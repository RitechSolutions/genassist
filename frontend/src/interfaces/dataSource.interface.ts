import type { ConnectionStatus } from "./connectionStatus.interface";
import type {
  ConditionalField,
  FieldSchema,
} from "./dynamicFormSchemas.interface";

/** Values stored in data source connection_data (tags fields use string[]). */
export type ConnectionDataValue = string | number | boolean | string[];

export interface DataSource {
  id?: string;
  name: string;
  source_type: string;
  connection_data: Record<string, ConnectionDataValue>;
  connection_status?: ConnectionStatus | null;
  is_active: number;
  oauth_status?: "connected" | "disconnected" | "pending" | "error";
  oauth_email?: string;
}

// Data source forms are rendered by the same schema pipeline as every other
// dynamic form, so these are the unified definitions under the older names.
export type { ConditionalField };
export type DataSourceField = FieldSchema;

export interface DataSourceConfig {
  name: string;
  fields: DataSourceField[];
}

export interface DataSourcesConfig {
  [key: string]: DataSourceConfig;
}
