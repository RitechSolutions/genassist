import { User } from "@/interfaces/user.interface";

export interface AuditLog {
  id: string;
  table_name: string;
  record_id: string;
  action_name: "Insert" | "Update" | "Delete";
  json_changes: Record<string, unknown>;
  modified_at: string;
  modified_by: string;
}

export interface AuditLogDetailsDialogProps {
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  auditLogId: string;
  users: User[];
}

export interface AuditLogCardProps {
  searchQuery: string;
  auditLogs: AuditLog[];
  users: User[];
  onViewDetails: (logId: string) => void;
  loading?: boolean;
  isRefreshing?: boolean;
  error?: string | null;
  onRetry?: () => void;
}
