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
    | "Other";
  values: Record<string, string>;
  description?: string;
  is_active: number;
  created_at?: string;
  updated_at?: string;
}
