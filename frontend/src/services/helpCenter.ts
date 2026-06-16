import { apiRequest } from "@/config/api";
import {
  SupportTicket,
  SupportTicketComment,
  SupportTicketCreatePayload,
  SupportTicketDuplicateCandidate,
  SupportTicketListResponse,
} from "@/interfaces/helpCenter.interface";

const BASE = "help-center/tickets";

export const listSupportTickets = async (params?: {
  status?: string;
  ticket_type?: string;
  skip?: number;
  limit?: number;
  mine_only?: boolean;
}): Promise<SupportTicketListResponse> => {
  const search = new URLSearchParams();
  if (params?.status) search.set("status", params.status);
  if (params?.ticket_type) search.set("ticket_type", params.ticket_type);
  if (params?.skip != null) search.set("skip", String(params.skip));
  if (params?.limit != null) search.set("limit", String(params.limit));
  if (params?.mine_only) search.set("mine_only", "true");
  const qs = search.toString();
  return (
    (await apiRequest<SupportTicketListResponse>("GET", `${BASE}${qs ? `?${qs}` : ""}`)) ?? {
      items: [],
      total: 0,
    }
  );
};

export const getSupportTicket = async (id: string): Promise<SupportTicket | null> => {
  return (await apiRequest<SupportTicket>("GET", `${BASE}/${id}`)) ?? null;
};

export const createSupportTicket = async (
  payload: SupportTicketCreatePayload
): Promise<SupportTicket> => {
  const data = await apiRequest<SupportTicket>("POST", BASE, payload as unknown as Record<string, unknown>);
  if (!data) throw new Error("Failed to create ticket");
  return data;
};

export const searchDuplicateTickets = async (
  title: string,
  ticket_type = "bug"
): Promise<SupportTicketDuplicateCandidate[]> => {
  const qs = new URLSearchParams({ title, ticket_type });
  return (
    (await apiRequest<SupportTicketDuplicateCandidate[]>("GET", `${BASE}/duplicates?${qs}`)) ?? []
  );
};

export const listTicketComments = async (ticketId: string): Promise<SupportTicketComment[]> => {
  return (await apiRequest<SupportTicketComment[]>("GET", `${BASE}/${ticketId}/comments`)) ?? [];
};

export const addTicketComment = async (
  ticketId: string,
  body: string
): Promise<SupportTicketComment> => {
  const data = await apiRequest<SupportTicketComment>("POST", `${BASE}/${ticketId}/comments`, {
    body,
  });
  if (!data) throw new Error("Failed to add comment");
  return data;
};
