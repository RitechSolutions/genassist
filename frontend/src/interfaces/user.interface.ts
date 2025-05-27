import { Role } from "./role.interface";
import { UserType } from "./userType.interface";
import { ApiKey } from "./api-key.interface";

export interface User {
    id?: string;
    username: string;
    email: string;
    password?: string;
    is_active: number;
    
    roles?: Role[];
    user_type?: UserType;
    api_keys?: ApiKey[];
    
    role_ids?: string[];
    user_type_id?: string;
    
    created_at?: string;
    updated_at?: string;
}

export interface UserProfile {
    id: string;
    username: string;
    email: string;
    permissions: string[];
  }