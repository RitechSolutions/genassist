import type { FieldValue } from './dynamicFormSchemas.interface';

export interface AppSetting {
  id: string;
  name: string;
  type:
    | "Zendesk"
    | "WhatsApp"
    | "Gmail"
    | "Microsoft"
    | "Slack"
    | "Jira"
    | "FileManagerSettings"
    | "Other";
  values: Record<string, FieldValue>;
  description?: string;
  is_active: number;
  created_at?: string;
  updated_at?: string;
}
