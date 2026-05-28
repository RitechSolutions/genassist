export type SupportTicketType = "bug" | "feature" | "question";

export interface SupportTicket {
  id: string;
  reporter_user_id: string;
  title: string;
  description: string;
  ticket_type: SupportTicketType;
  status: string;
  priority?: number | null;
  tags?: string[] | null;
  environment?: Record<string, unknown> | null;
  azure_work_item_id?: number | null;
  azure_project?: string | null;
  azure_url?: string | null;
  duplicate_of_id?: string | null;
  fingerprint?: string | null;
  vote_count: number;
  sync_error?: string | null;
  synced_at?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface SupportTicketDuplicateCandidate {
  id: string;
  title: string;
  status: string;
  vote_count: number;
  azure_work_item_id?: number | null;
  azure_url?: string | null;
  similarity?: string | null;
}

export interface SupportTicketListResponse {
  items: SupportTicket[];
  total: number;
}

export interface SupportTicketCreatePayload {
  title: string;
  description: string;
  ticket_type: SupportTicketType;
  priority?: number;
  tags?: string[];
  environment?: Record<string, unknown>;
  duplicate_of_id?: string;
  force_create?: boolean;
}

export interface SupportTicketComment {
  id: string;
  ticket_id: string;
  author_user_id: string;
  body: string;
  created_at?: string | null;
}
