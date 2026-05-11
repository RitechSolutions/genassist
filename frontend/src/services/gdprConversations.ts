import { apiRequest } from "@/config/api";

/**
 * Subset of the conversation list payload that the admin GDPR view needs to
 * render results. Defined locally so the admin view stays decoupled from the
 * full ``Transcript`` model used by the Conversations page.
 */
export interface GdprConversationItem {
  id: string;
  status: string | null;
  created_at: string | null;
  updated_at: string | null;
  is_deleted: number | null;
  pii_redacted_at?: string | null;
  zendesk_ticket_id?: number | null;
  topic?: string | null;
  custom_attributes?: Record<string, unknown> | null;
}

export interface GdprConversationListResponse {
  items: GdprConversationItem[];
  total: number;
  page: number;
  page_size: number;
  has_more: boolean;
}

export type GdprDeleteMode = "soft" | "anonymize" | "hard";

/**
 * Search conversations by an end-user email for GDPR Right-to-Erasure flows.
 *
 * The backend matches both ``custom_attributes.pii.requester_email`` (the
 * email captured by the Zendesk ticket node) and falls back to full-text
 * search over ``transcript_messages.text``. This function is intentionally
 * additive: it reuses the existing ``GET /conversations`` endpoint and
 * passes the new ``email`` query parameter without breaking other callers.
 */
export const searchConversationsByEmail = async (
  email: string,
  options?: { skip?: number; limit?: number },
): Promise<GdprConversationListResponse> => {
  const params = new URLSearchParams();
  params.set("email", email);
  params.set("skip", String(options?.skip ?? 0));
  params.set("limit", String(options?.limit ?? 20));
  // Keep the response light; messages are not needed for the admin list.
  params.set("include_messages", "false");

  const response = await apiRequest<GdprConversationListResponse>(
    "GET",
    `/conversations?${params.toString()}`,
  );

  if (!response) {
    return { items: [], total: 0, page: 1, page_size: options?.limit ?? 20, has_more: false };
  }
  return response;
};

/**
 * Trigger the admin GDPR deletion endpoint for a single conversation. The
 * caller picks the ``mode`` (``soft``/``anonymize``/``hard``); the backend
 * defaults are also honored if ``mode`` is omitted.
 */
export const deleteConversationForGdpr = async (
  conversationId: string,
  mode: GdprDeleteMode,
): Promise<void> => {
  await apiRequest<void>(
    "DELETE",
    `/conversations/${conversationId}/gdpr?mode=${encodeURIComponent(mode)}`,
  );
};
