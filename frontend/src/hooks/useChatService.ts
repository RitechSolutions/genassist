import { useCallback, useEffect, useRef, useState } from "react";
import { ChatService, type AgentWelcomeData, type ChatMessage } from "genassist-chat-react";

export interface UseChatServiceOptions {
  /** Called for every incoming message (agent, customer, special). */
  onMessage: (message: ChatMessage) => void;
  /** Called when the agent sends welcome data (title, FAQs, etc.). */
  onWelcomeData?: (data: AgentWelcomeData) => void;
  /** When this value changes the conversation resets automatically. */
  scopeId?: string;
}

export interface UseChatServiceReturn {
  /** Send a text message. Starts a conversation first if needed. */
  sendMessage: (text: string) => Promise<void>;
  /** Forget the current conversation and start fresh on next send. */
  resetConversation: () => void;
  /** Whether the required env vars (API URL + key) are configured. */
  hasConfig: boolean;
  /** Direct ref to the underlying ChatService for advanced use. */
  chatRef: React.RefObject<ChatService | null>;
  /** Start a conversation without sending a message (useful for pre-warming). */
  startConversationIfNeeded: () => Promise<void>;
}

/**
 * Low-level hook that manages a ChatService lifecycle:
 * – reads env vars for API URL, key, and tenant
 * – creates / tears down the ChatService instance
 * – exposes `sendMessage` which lazily starts a conversation
 * – resets on `scopeId` change
 *
 * Domain-specific logic (action parsing, workflow draft extraction, etc.)
 * belongs in the consuming hook, not here.
 */
export function useChatService({
  onMessage,
  onWelcomeData,
  scopeId,
}: UseChatServiceOptions): UseChatServiceReturn {
  const chatRef = useRef<ChatService | null>(null);
  const isMountedRef = useRef(true);
  const isStartingRef = useRef(false);
  const prevScopeRef = useRef(scopeId);

  const baseUrl = (import.meta.env.VITE_ONBOARDING_API_URL as string) || "";
  const apiKey = (import.meta.env.VITE_ONBOARDING_CHAT_APIKEY as string) || "";
  const tenant =
    (localStorage.getItem("tenant_id") as string | null) || undefined;

  const [hasConfig] = useState(() => Boolean(baseUrl && apiKey));

  // Keep callbacks in a ref so the ChatService handler always sees the latest
  const onMessageRef = useRef(onMessage);
  onMessageRef.current = onMessage;
  const onWelcomeDataRef = useRef(onWelcomeData);
  onWelcomeDataRef.current = onWelcomeData;

  // ── Lifecycle: create & wire up ChatService ──
  useEffect(() => {
    if (!hasConfig) return;

    const chat = new ChatService(
      baseUrl,
      undefined,
      apiKey,
      undefined,
      tenant,
      undefined,
      false,
      false,
    );
    chatRef.current = chat;
    chat.resetChatConversation();

    chat.setMessageHandler((message: ChatMessage) => {
      if (!isMountedRef.current) return;
      onMessageRef.current(message);
    });

    if (onWelcomeDataRef.current) {
      chat.setWelcomeDataHandler((data: AgentWelcomeData) => {
        if (!isMountedRef.current) return;
        onWelcomeDataRef.current?.(data);
      });
    }

    return () => {
      chat.setWelcomeDataHandler?.(null);
      chat.disconnect();
      chatRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [baseUrl, apiKey, tenant, hasConfig]);

  // ── Unmount guard ──
  useEffect(() => {
    return () => {
      isMountedRef.current = false;
    };
  }, []);

  // ── Scope change → reset conversation ──
  useEffect(() => {
    if (
      prevScopeRef.current !== undefined &&
      scopeId !== prevScopeRef.current
    ) {
      chatRef.current?.resetChatConversation();
    }
    prevScopeRef.current = scopeId;
  }, [scopeId]);

  // ── Start conversation (idempotent) ──
  const startConversationIfNeeded = useCallback(async () => {
    const chat = chatRef.current;
    if (!chat || isStartingRef.current) return;

    const existing = chat.getConversationId?.();
    if (existing) return;

    isStartingRef.current = true;
    try {
      await chat.startConversation(undefined);
    } finally {
      isStartingRef.current = false;
    }
  }, []);

  // ── Send message ──
  const sendMessage = useCallback(
    async (text: string) => {
      if (!chatRef.current) return;
      await startConversationIfNeeded();
      await chatRef.current.sendMessage(text);
    },
    [startConversationIfNeeded],
  );

  const resetConversation = useCallback(() => {
    chatRef.current?.resetChatConversation();
  }, []);

  return {
    sendMessage,
    resetConversation,
    hasConfig,
    chatRef,
    startConversationIfNeeded,
  };
}
