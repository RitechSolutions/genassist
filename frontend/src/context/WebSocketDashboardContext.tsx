import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { useWebSocket } from "@/hooks/useWebSocket";
import { ActiveConversation } from "@/interfaces/liveConversation.interface";
import {
  ConversationDataPayload,
  ConversationListPayload,
  ConversationUpdatePayload,
  FinalizePayload,
} from "@/interfaces/websocket.interface";
import { conversationService } from "@/services/liveConversations";

const DEFAULT_TOPICS = ["message", "statistics", "finalize", "hostile", "update"] as const;
const EFFECTIVE_TOPICS = Array.from(
  new Set([...DEFAULT_TOPICS, "message", "hostile", "update"])
);

export interface WebSocketDashboardContextValue {
  conversations: ActiveConversation[];
  total: number;
  isConnected: boolean;
  error: Error | null;
  refetch: () => void;
  finalizedIds: string[];
  resyncHint: number;
}

const WebSocketDashboardContext =
  createContext<WebSocketDashboardContextValue | null>(null);

function applyCachedTopic(conv: ActiveConversation): ActiveConversation {
  const provided = (conv.topic || "").trim();
  if (provided && provided !== "Unknown") {
    try {
      conversationService.setCachedTopic(conv.id, provided);
    } catch {
      // ignore
    }
    return conv;
  }
  const cached = conversationService.getCachedTopic(conv.id);
  return cached ? { ...conv, topic: cached } : conv;
}

function getConversationIdFromPayload(data: Record<string, unknown>): string | undefined {
  const p = (data?.payload || {}) as {
    conversation_id?: string;
    id?: string;
    conversation?: { id?: string };
  };
  return (
    p.conversation_id ||
    p.id ||
    p?.conversation?.id ||
    (data.conversation_id as string) ||
    (data.id as string) ||
    undefined
  );
}

export function WebSocketDashboardProvider({
  children,
  token,
}: {
  children: React.ReactNode;
  token: string;
}) {
  const [conversations, setConversations] = useState<ActiveConversation[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [finalizedIds, setFinalizedIds] = useState<string[]>([]);
  const [resyncHint, setResyncHint] = useState<number>(0);

  const handleMessage = useCallback((data: Record<string, unknown>) => {
    const topic = (data.topic || data.type) as string;

    switch (topic) {
      case "conversation_list": {
        const payload = data.payload as ConversationListPayload;
        if (Array.isArray(payload.conversations)) {
          const incoming = payload.conversations.map(applyCachedTopic);
          setConversations(incoming);
          if (typeof payload.total === "number" && payload.total >= 0) {
            setTotal(payload.total);
          }
        }
        break;
      }
      case "statistics": {
        const stats = data.payload as { conversation_id?: string; topic?: string };
        if (!stats?.conversation_id || typeof stats.topic !== "string" || stats.topic.trim() === "") break;
        try {
          conversationService.setCachedTopic(stats.conversation_id, stats.topic);
        } catch {
          // ignore
        }
        setConversations((prev) =>
          prev.map((c) =>
            c.id === stats.conversation_id ? { ...c, topic: stats.topic as string } : c
          )
        );
        break;
      }
      case "update": {
        const payload = data.payload as ConversationDataPayload;
        const convId = payload?.conversation_id != null
          ? String(payload.conversation_id)
          : undefined;
        if (!convId) return;

        const status = (payload as { status?: string })?.status;
        if (status === "finalized" || status === "completed") {
          setConversations((prev) =>
            prev.filter((c) => c.id !== convId)
          );
          setTotal((prev) => Math.max(0, prev - 1));
          return;
        }

        setConversations((prev) => {
          const index = prev.findIndex((c) => c.id === convId);
          const existing = index !== -1 ? prev[index] : undefined;
          const merged: ActiveConversation = {
            id: convId,
            type: existing?.type || "chat",
            status: existing?.status || "in-progress",
            transcript:
              Array.isArray((payload as { messages?: unknown }).messages)
                ? (payload as { messages?: unknown }).messages as ActiveConversation["transcript"]
                : typeof payload.transcript === "string"
                  ? payload.transcript
                  : Array.isArray(payload.transcript)
                    ? (payload.transcript as ActiveConversation["transcript"])
                    : existing?.transcript || "",
            sentiment: existing?.sentiment || "neutral",
            timestamp:
              payload.create_time ||
              existing?.timestamp ||
              new Date().toISOString(),
            in_progress_hostility_score:
              payload.in_progress_hostility_score ??
              existing?.in_progress_hostility_score ??
              0,
            duration: payload.duration ?? existing?.duration,
            word_count: payload.word_count ?? existing?.word_count,
            agent_ratio: payload.agent_ratio ?? existing?.agent_ratio,
            customer_ratio: payload.customer_ratio ?? existing?.customer_ratio,
            supervisor_id: payload.supervisor_id ?? existing?.supervisor_id ?? null,
            topic: payload.topic ?? existing?.topic,
            negative_reason:
              (payload as { negative_reason?: string }).negative_reason ??
              existing?.negative_reason,
          };
          const enhanced = applyCachedTopic(merged);
          if (index !== -1) {
            const copy = [...prev];
            copy[index] = enhanced;
            return copy;
          }
          return [...prev, enhanced];
        });
        setResyncHint((n) => n + 1);
        break;
      }
      case "conversation_update": {
        const payload = data.payload as ConversationUpdatePayload;
        setConversations((prev) => {
          const enhancedConv = applyCachedTopic(payload.conversation);
          const index = prev.findIndex((c) => c.id === payload.conversation.id);
          if (payload.action === "removed") {
            return prev.filter((c) => c.id !== payload.conversation.id);
          }
          if (index !== -1) {
            const copy = [...prev];
            copy[index] = enhancedConv;
            return copy;
          }
          return [...prev, enhancedConv];
        });
        break;
      }
      case "finalize": {
        const payload = data.payload as FinalizePayload;
        const conversationId =
          payload?.conversation_id || payload?.id || getConversationIdFromPayload(data);

        if (conversationId) {
          setConversations((prev) =>
            prev.filter((c) => c.id !== conversationId)
          );
          setTotal((prev) => Math.max(0, prev - 1));
          try {
            conversationService.removeCachedTopic(conversationId);
          } catch {
            // ignore
          }
          setFinalizedIds((prev) => [...prev, conversationId]);
        } else {
          setConversations((prev) => {
            const idx = prev.findIndex(
              (c) => c.status !== "in-progress" && c.status !== "takeover"
            );
            if (idx !== -1) {
              const copy = [...prev];
              const removed = copy.splice(idx, 1);
              if (removed[0]) {
                setFinalizedIds((p) => [...p, removed[0].id]);
              }
              return copy;
            }
            return prev;
          });
          setResyncHint((n) => n + 1);
        }
        break;
      }
      case "takeover": {
        const payload = data.payload as {
          conversation_id?: string;
          supervisor_id?: string;
        };
        if (payload?.conversation_id) {
          setConversations((prev) =>
            prev.map((c) =>
              c.id === payload.conversation_id
                ? {
                    ...c,
                    status: "takeover" as const,
                    supervisor_id: payload.supervisor_id || c.supervisor_id,
                  }
                : c
            )
          );
        }
        break;
      }
      default:
        break;
    }
  }, []);

  const { isConnected, error, refetch } = useWebSocket({
    roomType: "dashboard",
    token,
    topics: EFFECTIVE_TOPICS,
    lang: "en",
    onMessage: handleMessage,
    reconnect: true,
    maxReconnectAttempts: 5,
  });

  const value = useMemo<WebSocketDashboardContextValue>(
    () => ({
      conversations,
      total,
      isConnected,
      error,
      refetch,
      finalizedIds,
      resyncHint,
    }),
    [
      conversations,
      total,
      isConnected,
      error,
      refetch,
      finalizedIds,
      resyncHint,
    ]
  );

  return (
    <WebSocketDashboardContext.Provider value={value}>
      {children}
    </WebSocketDashboardContext.Provider>
  );
}

export function useWebSocketDashboardContext(): WebSocketDashboardContextValue {
  const ctx = useContext(WebSocketDashboardContext);
  if (!ctx) {
    return {
      conversations: [],
      total: 0,
      isConnected: false,
      error: null,
      refetch: () => {},
      finalizedIds: [],
      resyncHint: 0,
    };
  }
  return ctx;
}
