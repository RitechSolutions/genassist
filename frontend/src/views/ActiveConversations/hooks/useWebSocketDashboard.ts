import { useEffect, useRef, useState } from "react";
import { getWsUrl, isWsEnabled } from "@/config/api";
import {
  DashboardWebSocketMessage,
  UseWebSocketDashboardOptions,
  ConversationListPayload,
  ConversationUpdatePayload,
  ConversationDataPayload,
  FinalizePayload
} from "@/interfaces/websocket.interface";
import { ActiveConversation } from "@/interfaces/liveConversation.interface";
import { conversationService } from "@/services/liveConversations";
import { getTenantId } from "@/services/auth";

export function useWebSocketDashboard({
  token,
  lang = "en",
  topics = ["message", "statistics", "finalize", "hostile"]
}: UseWebSocketDashboardOptions) {
  const [conversations, setConversations] = useState<ActiveConversation[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [finalizedIds, setFinalizedIds] = useState<string[]>([]);
  const [resyncHint, setResyncHint] = useState<number>(0);
  const socketRef = useRef<WebSocket | null>(null);
  const reconnectAttempts = useRef(0);

  const connect = async () => {
    if (!isWsEnabled) return;
    try {
      const wsBaseUrl = await getWsUrl();
      const topicsQuery = topics.map(t => `topics=${t}`).join("&");
      const tenant = getTenantId();
      const tenantParam = tenant ? `&x-tenant-id=${tenant}` : "";
      const wsUrl = `${wsBaseUrl}/conversations/ws/dashboard/list?access_token=${token}&lang=${lang}&${topicsQuery}${tenantParam}`;

      const socket = new WebSocket(wsUrl);
      socketRef.current = socket;

      socket.onopen = () => {
        setIsConnected(true);
        setError(null);
        reconnectAttempts.current = 0;
      };

      socket.onmessage = (event) => {
        try {
          const data: DashboardWebSocketMessage = JSON.parse(event.data);

          const applyCachedTopic = (conv: ActiveConversation): ActiveConversation => {
            const provided = (conv.topic || "").trim();
            if (provided && provided !== "Unknown") {
              try { conversationService.setCachedTopic(conv.id, provided); } catch (err)
              { // ignore 
              }
              return conv;
            }
            const cached = conversationService.getCachedTopic(conv.id);
            return cached ? { ...conv, topic: cached } : conv;
          };

          const getConversationId = (): string | undefined => {
            const anyData = data as unknown as { payload?: unknown; conversation_id?: string; id?: string };
            const p = (anyData?.payload || {}) as { conversation_id?: string; id?: string; conversation?: { id?: string } };
            return (
              p.conversation_id ||
              p.id ||
              p?.conversation?.id ||
              anyData.conversation_id ||
              anyData.id ||
              undefined
            );
          };

          switch (data.topic || data.type) {
            case "conversation_list": {
              const payload = data.payload as ConversationListPayload;
              // Merge conversations instead of replacing the full list
              if (Array.isArray(payload.conversations) && payload.conversations.length > 0) {
                const incoming = payload.conversations.map(applyCachedTopic);
                setConversations(prev => {
                  const map = new Map(prev.map(c => [c.id, c] as const));
                  for (const conv of incoming) {
                    map.set(conv.id, conv);
                  }
                  return Array.from(map.values());
                });
                if (typeof payload.total === "number" && payload.total >= 0) {
                  setTotal(payload.total);
                }
              }
              break;
            }
            case "statistics": {
              const stats = data.payload as { conversation_id?: string; topic?: string };
              if (!stats || !stats.conversation_id) break;
              if (typeof stats.topic !== "string" || stats.topic.trim() === "") break;
              try { conversationService.setCachedTopic(stats.conversation_id, stats.topic as string); } catch (err)
              { 
                // ignore
              }
              setConversations(prev => prev.map(c => c.id === stats.conversation_id ? { ...c, topic: stats.topic as string } : c));
              break;
            }
            case "update": {
              const payload = data.payload as ConversationDataPayload;
              if (!payload.conversation_id) return;
              
              // Check if conversation is finalized/completed in the update
              const status = (payload as unknown as { status?: string })?.status;
              if (status === "finalized" || status === "completed") {
                setConversations(prev => prev.filter(c => c.id !== payload.conversation_id));
                setTotal(prev => Math.max(0, prev - 1));
                return;
              }
              
              setConversations(prev => {
                const index = prev.findIndex(c => c.id === payload.conversation_id);
                const existing = index !== -1 ? prev[index] : undefined;
                const merged: ActiveConversation = {
                  id: payload.conversation_id,
                  type: existing?.type || "chat",
                  status: existing?.status || "in-progress",
                  transcript: (Array.isArray((payload as { messages?: unknown }).messages)
                    ? ((payload as { messages?: unknown }).messages as ActiveConversation["transcript"]) 
                    : (typeof payload.transcript === "string"
                        ? payload.transcript
                        : (Array.isArray(payload.transcript)
                          ? (payload.transcript as ActiveConversation["transcript"]) 
                          : existing?.transcript || ""))),
                  sentiment: existing?.sentiment || "neutral",
                  timestamp: payload.create_time || existing?.timestamp || new Date().toISOString(),
                  in_progress_hostility_score: payload.in_progress_hostility_score ?? existing?.in_progress_hostility_score ?? 0,
                  duration: payload.duration ?? existing?.duration,
                  word_count: payload.word_count ?? existing?.word_count,
                  agent_ratio: payload.agent_ratio ?? existing?.agent_ratio,
                  customer_ratio: payload.customer_ratio ?? existing?.customer_ratio,
                  supervisor_id: payload.supervisor_id ?? existing?.supervisor_id ?? null,
                  topic: payload.topic ?? existing?.topic,
                  negative_reason: (payload as { negative_reason?: string }).negative_reason ?? existing?.negative_reason,
                };
                const enhanced = applyCachedTopic(merged);
                if (index !== -1) {
                  const copy = [...prev];
                  copy[index] = enhanced;
                  return copy;
                }
                return [...prev, enhanced];
              });
              break;
            }
            case "conversation_update": {
              const payload = data.payload as ConversationUpdatePayload;
              setConversations(prev => {
                const enhancedConv = applyCachedTopic(payload.conversation);
                const index = prev.findIndex(c => c.id === payload.conversation.id);
                if (payload.action === "removed") {
                  return prev.filter(c => c.id !== payload.conversation.id);
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
              // Handle conversation finalization remove from active list
              const payload = data.payload as FinalizePayload;
              const conversationId = payload?.conversation_id || payload?.id || getConversationId();
              if (conversationId) {
                setConversations(prev => {
                  const filtered = prev.filter(c => c.id !== conversationId);
                  return filtered;
                });
                setTotal(prev => Math.max(0, prev - 1));
                try { conversationService.removeCachedTopic(conversationId); } catch (err)
                { // ignore
                }
                setFinalizedIds(prev => [...prev, conversationId]);
              } else {
                // Fallback: if payload is empty, try to infer the most recently updated conversation
                // with status change via an implicit rule: remove the last item if it has status not in_progress/takeover
                setConversations(prev => {
                  const idx = prev.findIndex(c => c.status !== "in-progress" && c.status !== "takeover");
                  if (idx !== -1) {
                    const copy = [...prev];
                    const removed = copy.splice(idx, 1);
                    if (removed[0]) setFinalizedIds(p => [...p, removed[0].id]);
                    return copy;
                  }
                  return prev;
                });
                // Resync via HTTP to ensure consistency
                setResyncHint((n) => n + 1);
              }
              break;
            }
            case "takeover": {
              // Handle takeover event update conversation status
              const payload = data.payload as { conversation_id?: string; supervisor_id?: string };
              if (payload.conversation_id) {
                setConversations(prev => prev.map(c => 
                  c.id === payload.conversation_id 
                    ? { ...c, status: "takeover" as const, supervisor_id: payload.supervisor_id || c.supervisor_id }
                    : c
                ));
              }
              break;
            }
            default:
              break;
          }
        } catch (err) {
          // ignore
        }
      };

      socket.onerror = (e) => {
        setError(new Error("WebSocket error"));
      };

      socket.onclose = () => {
        setIsConnected(false);
        if (reconnectAttempts.current < 5) {
          reconnectAttempts.current++;
          setTimeout(connect, Math.min(1000 * reconnectAttempts.current, 10000));
        } else {
          setError(new Error("Failed to reconnect"));
        }
      };
    } catch (e) {
      setError(e as Error);
    }
  };

  useEffect(() => {
    if (!isWsEnabled) return;
    connect();
    return () => socketRef.current?.close();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, lang, topics.join(",")]);

  const refetch = () => {
    if (socketRef.current?.readyState !== WebSocket.OPEN) connect();
  };

  return { conversations, total, isConnected, error, refetch, finalizedIds, resyncHint };
}
