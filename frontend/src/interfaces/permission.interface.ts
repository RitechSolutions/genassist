export interface Permission {
    id: string;
    name: string;
    is_active: number;
    description?: string | null;
    /** Reserved for the built-in admin role; the API rejects it for any other role. */
    is_admin_only?: boolean;
  }
