import { useEffect, useRef, useState } from "react";
import { TranscriptEntry } from "@/interfaces/transcript.interface";
import { getWsUrl, getWsVersion, isWsEnabled } from "@/config/api";
import { UseWebSocketTranscriptOptions, StatisticsPayload, TakeoverPayload } from "@/interfaces/websocket.interface";
import { getTenantId } from "@/services/auth";

function toEpochMs(ct: string | number | undefined | null): number {
  if (ct == null) return 0;
  if (typeof ct === "number") return ct;
  const t = new Date(ct).getTime();
  return isNaN(t) ? 0 : t;
}

export function useWebSocketTranscript({
  conversationId,
  token,
  transcriptInitial = [],
  lang = "en",
}: UseWebSocketTranscriptOptions) {
  const [messages, setMessages] = useState<TranscriptEntry[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [statistics, setStatistics] = useState<StatisticsPayload>({});
  const [takeoverInfo, setTakeoverInfo] = useState<TakeoverPayload>({});
  const socketRef = useRef<WebSocket | null>(null);
  const lastConversationIdRef = useRef<string | null>(null);
  const transcriptInitialRef = useRef(transcriptInitial);
  transcriptInitialRef.current = transcriptInitial;

  useEffect(() => {
    if (!isWsEnabled || !conversationId || !token) return;

    if (lastConversationIdRef.current === conversationId) return;

    lastConversationIdRef.current = conversationId;

    let cancelled = false;
    let socket: WebSocket | null = null;

    const topics = ["message", "statistics", "finalize", "takeover"];
    const queryString = topics.map((t) => `topics=${t}`).join("&");
    const tenant = getTenantId();
    const tenantParam = tenant ? `&x-tenant-id=${tenant}` : "";
    const langParam = lang ? `&lang=${lang}` : "";

    getWsUrl()
    .then((wsBaseUrl) => {
        if (cancelled || !isWsEnabled) return;
        const wsVersion = getWsVersion();
        let wsUrl = "";
        if (wsVersion === 1) {
          // old websocket service (WS is co-hosted with the HTTP API under /api)
          wsUrl = `${wsBaseUrl}/conversations/ws/${conversationId}?access_token=${token}&${queryString}${tenantParam}`;
        } else {
          wsUrl = `${wsBaseUrl}/ws/conversations/${conversationId}?access_token=${token}${langParam}&${queryString}${tenantParam}`;
        }

        socket = new WebSocket(wsUrl);
        socketRef.current = socket;
        console.log("[WebSocket Transcript] Connecting", { wsUrl, conversationId, wsVersion });

        socket.onopen = () => {
          console.log("[WebSocket Transcript] Connected", { conversationId });
          if (!cancelled) {
            setIsConnected(true);
            setMessages(transcriptInitialRef.current);
          }
        };

        socket.onmessage = (event) => {
          if (cancelled) return;

          try {
            const data = JSON.parse(event.data);
            console.log("[WebSocket Transcript] Message", { conversationId, type: data.type ?? data.topic, payload: data.payload });

            if ((data.topic === "message" || data.type === "message") && data.payload) {
              const newEntries = Array.isArray(data.payload)
                ? data.payload
                : [data.payload];

              setMessages((prev) => {
                const combined = [...prev];
                for (const entry of newEntries) {
                  const exists = combined.some(
                    (msg) =>
                      msg.text === entry.text &&
                      toEpochMs(msg.create_time) === toEpochMs(entry.create_time)
                  );
                  if (!exists) {
                    combined.push(entry);
                  }
                }
                return combined;
              });
            }

            if ((data.topic === "statistics" || data.type === "statistics") && data.payload) {
              setStatistics((prev) => ({
                ...prev,
                ...data.payload,
              }));
            }

            if (data.topic === "takeover" || data.type === "takeover") {
              setTakeoverInfo({
                supervisor_id: data.payload?.supervisor_id,
                user_id: data.payload?.user_id,
                timestamp: new Date().toISOString(),
              });
            }
          } catch (e) {
            // ignore
          }
        };

        socket.onerror = (e) => {
          console.warn("[WebSocket Transcript] Error", { conversationId, event: e });
        };

        socket.onclose = (event) => {
          console.log("[WebSocket Transcript] Closed", { conversationId, code: event.code, reason: event.reason, wasClean: event.wasClean });
          if (!cancelled) {
            setIsConnected(false);
            lastConversationIdRef.current = null;
          }
        };
      })
      .catch(() => {
        // getWsUrl rejects when VITE_WS=false; no socket to clean up
      });

    return () => {
      cancelled = true;
      if (socket) {
        socket.close();
        socketRef.current = null;
      }
      lastConversationIdRef.current = null;
    };
  }, [conversationId, token, lang]);

  const sendMessage = (entry: TranscriptEntry) => {
    if (socketRef.current && socketRef.current.readyState === WebSocket.OPEN) {
      socketRef.current.send(JSON.stringify(entry));
    } else {
      // ignore
    }
  };

  return {
    messages,
    isConnected,
    sendMessage,
    statistics,
    takeoverInfo
  };
}