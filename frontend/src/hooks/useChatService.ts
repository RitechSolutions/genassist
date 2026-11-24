import { useCallback, useEffect, useRef, useState } from "react";
import { ChatService, type AgentWelcomeData, type ChatMessage, type StreamEvent } from "genassist-chat-react";

export interface UseChatServiceOptions {
  /** Called for every incoming message (agent, customer, special). */
  onMessage: (message: ChatMessage) => void;
  /** Called for each progress frame of a streamed turn (reply text, activity, narrated steps). */
  onStream?: (event: StreamEvent) => void;
  /** Called when the agent sends welcome data (title, FAQs, etc.). */
  onWelcomeData?: (data: AgentWelcomeData) => void;
  /** When this value changes the conversation resets automatically. */
  scopeId?: string;
  /**
   * A conversation to continue instead of starting fresh, for the current
   * scope. The service resumes it (same id, so the agent keeps its memory);
   * when absent the scope starts with no conversation.
   */
  resume?: SavedConversation | null;
}

/** What is needed to pick a conversation up again later. */
export interface SavedConversation {
  conversationId: string;
  createTime: number;
}

// The plugin keeps its current conversation under this key, one per API key.
const PLUGIN_STORAGE_BASE = "genassist_conversation";

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
  /** The current conversation, in the form needed to resume it later. */
  getConversationState: () => SavedConversation | null;
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
  onStream,
  onWelcomeData,
  scopeId,
  resume = null,
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
  const onStreamRef = useRef(onStream);
  onStreamRef.current = onStream;
  const onWelcomeDataRef = useRef(onWelcomeData);
  onWelcomeDataRef.current = onWelcomeData;
  const resumeRef = useRef(resume);
  resumeRef.current = resume;

  const pluginKey = `${PLUGIN_STORAGE_BASE}:${apiKey}`;

  // Point the service at a saved conversation: the plugin reads its own storage
  // key, so the saved id is written there and reloaded.
  const applyResume = useCallback(
    (chat: ChatService) => {
      const saved = resumeRef.current;
      chat.resetChatConversation();
      if (!saved?.conversationId) return;
      try {
        localStorage.setItem(
          pluginKey,
          JSON.stringify({ conversationId: saved.conversationId, createTime: saved.createTime, isFinalized: false })
        );
        (chat as unknown as { loadSavedConversation?: () => void }).loadSavedConversation?.();
      } catch {
        // Storage may be unavailable (privacy mode): start fresh.
      }
    },
    [pluginKey]
  );

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
    applyResume(chat);

    chat.setMessageHandler((message: ChatMessage) => {
      if (!isMountedRef.current) return;
      onMessageRef.current(message);
    });
    chat.setStreamHandler((event: StreamEvent) => {
      if (!isMountedRef.current) return;
      onStreamRef.current?.(event);
    });

    if (onWelcomeDataRef.current) {
      chat.setWelcomeDataHandler((data: AgentWelcomeData) => {
        if (!isMountedRef.current) return;
        onWelcomeDataRef.current?.(data);
      });
    }

    return () => {
      chat.setWelcomeDataHandler?.(null);
      chat.setStreamHandler(null);
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
      if (chatRef.current) applyResume(chatRef.current);
    }
    prevScopeRef.current = scopeId;
  }, [scopeId, applyResume]);

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

  const getConversationState = useCallback((): SavedConversation | null => {
    const conversationId = chatRef.current?.getConversationId?.();
    if (!conversationId) return null;
    try {
      const raw = localStorage.getItem(pluginKey);
      const createTime = raw ? (JSON.parse(raw) as { createTime?: number }).createTime : undefined;
      return { conversationId, createTime: typeof createTime === "number" ? createTime : Date.now() };
    } catch {
      return { conversationId, createTime: Date.now() };
    }
  }, [pluginKey]);

  return {
    sendMessage,
    resetConversation,
    hasConfig,
    chatRef,
    startConversationIfNeeded,
    getConversationState,
  };
}
