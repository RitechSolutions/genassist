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
  /** When set, the previous raw secret is still accepted by the API until this instant (ISO UTC). */
  previous_hashed_expires_at?: string | null;
  /** When set, API auth rejects this key at or after this instant (ISO UTC). */
  credential_expires_at?: string | null;
  /** Stored expiry selection in days (30/90/180/365). Null/undefined means Never. */
  credential_expiry_days?: number | null;
  /** Only used when creating a key (days until credential_expires_at). */
  expires_in_days?: number;
}