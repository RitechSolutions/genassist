/** Browser-storage keys for a conversation's cached messages and read-receipt state. */

export function buildMessagesStorageKey(apiKey: string, conversationId: string | null): string | null {
  if (!conversationId) return null;
  return `genassist_conversation_messages:${apiKey}:${conversationId}`;
}

export function buildReadStateStorageKey(apiKey: string, conversationId: string | null): string | null {
  if (!conversationId) return null;
  return `genassist_conversation_read_state:${apiKey}:${conversationId}`;
}

/** Removes the cached messages and read state of a conversation from this browser. */
export function removeStoredConversationData(apiKey: string, conversationId: string | null): void {
  const keys = [
    buildMessagesStorageKey(apiKey, conversationId),
    buildReadStateStorageKey(apiKey, conversationId),
  ];
  for (const key of keys) {
    if (!key) continue;
    try {
      localStorage.removeItem(key);
    } catch {
      // Storage may be unavailable (privacy mode); nothing to clean up then.
    }
  }
}
