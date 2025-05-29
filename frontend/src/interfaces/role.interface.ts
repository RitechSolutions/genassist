import { Permission } from "./permission.interface";

export interface Role {
    id: string;
    name: string;
    is_active: number;
    role_type?: string;
    created_at: string;
    updated_at: string;
    permissions: Permission[];
  }