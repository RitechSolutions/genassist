import { Permission } from "./permission.interface";

export interface Role {
    id: string;
    name: string;
    is_active: number;
    created_at: string;
    updated_at: string;
    permissions: Permission[];
  }