export interface AppSetting {
  id: string;
  key: string;
  value: string;
  description: string;
  is_active: number;
  encrypted: number;
  created_at?: string;
  updated_at?: string;
} 