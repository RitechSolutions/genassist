import { Role } from "./role.interface";

export interface ApiKey {
  id: string;
  key?: string;
  name: string;
  is_active: number;
  created_at?: string;
  updated_at?: string;
  user_id: string;
  assigned_user_id?: string;
  roles?: Role[];
  role_ids?: string[];
  masked_value?: string;
  key_val?: string;
  agent_id: string; 
}