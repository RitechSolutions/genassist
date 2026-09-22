export type ConversationsViewMode = "list" | "split";

export const CONVERSATIONS_VIEW_STORAGE_KEY = "genassist_conversations_view";

/** Reads the Conversations view mode from the URL first, then the last one the user picked. */
export function readConversationsViewMode(params: URLSearchParams): ConversationsViewMode {
  const fromUrl = params.get("view");
  if (fromUrl === "split" || fromUrl === "list") return fromUrl;
  try {
    return localStorage.getItem(CONVERSATIONS_VIEW_STORAGE_KEY) === "split" ? "split" : "list";
  } catch {
    // a blocked localStorage just means no remembered preference
    return "list";
  }
}
