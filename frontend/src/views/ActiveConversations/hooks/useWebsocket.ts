import { useEffect, useRef, useState, useCallback } from "react";
import { TranscriptEntry } from "@/interfaces/transcript.interface";
import { getWsUrl, isWsEnabled } from "@/config/api";
import { UseWebSocketTranscriptOptions, StatisticsPayload, TakeoverPayload } from "@/interfaces/websocket.interface";
import { getTenantId } from "@/services/auth";

const MAX_RECONNECT_ATTEMPTS = 10;
const BASE_DELAY_MS = 1000;
const MAX_DELAY_MS = 30000;

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
}: UseWebSocketTranscriptOptions) {
  const [messages, setMessages] = useState<TranscriptEntry[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [statistics, setStatistics] = useState<StatisticsPayload>({});
  const [takeoverInfo, setTakeoverInfo] = useState<TakeoverPayload>({});
  const socketRef = useRef<WebSocket | null>(null);
  const reconnectAttempts = useRef(0);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const cancelledRef = useRef(false);

  const connect = useCallback(async () => {
    if (!isWsEnabled || !conversationId || !token || cancelledRef.current) return;

    try {
      const wsBaseUrl = await getWsUrl();
      if (cancelledRef.current) return;

      const topics = ["message", "statistics", "finalize", "takeover"];
      const queryString = topics.map((t) => `topics=${t}`).join("&");
      const tenant = getTenantId();
      const tenantParam = tenant ? `&x-tenant-id=${tenant}` : "";
      const wsUrl = `${wsBaseUrl}/ws/conversations/${conversationId}?access_token=${token}&lang=en&${queryString}${tenantParam}`;

      const socket = new WebSocket(wsUrl);
      socketRef.current = socket;

      socket.onopen = () => {
        if (cancelledRef.current) return;
        setIsConnected(true);
        reconnectAttempts.current = 0;
        // Only set initial messages on first connect (not reconnects)
        setMessages((prev) => (prev.length === 0 ? transcriptInitial : prev));
      };

      socket.onmessage = (event) => {
        if (cancelledRef.current) return;
        try {
          const data = JSON.parse(event.data);

          // Respond to server-side heartbeat pings
          if (data.type === "ping") {
            socket.send(JSON.stringify({ type: "pong" }));
            return;
          }

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
          // ignore parse errors
        }
      };

      socket.onerror = (event) => {
        console.warn("[WebSocket] error", { conversationId, event });
      };

      socket.onclose = (event) => {
        if (event.code !== 1000) {
          console.warn("[WebSocket] closed", {
            conversationId,
            code: event.code,
            reason: event.reason || "(none)",
            clean: event.wasClean,
          });
        }
        if (cancelledRef.current) return;
        setIsConnected(false);

        if (reconnectAttempts.current < MAX_RECONNECT_ATTEMPTS) {
          const delay = Math.min(
            BASE_DELAY_MS * Math.pow(2, reconnectAttempts.current),
            MAX_DELAY_MS
          );
          reconnectAttempts.current++;
          reconnectTimerRef.current = setTimeout(connect, delay);
        }
      };
    } catch {
      // getWsUrl rejects when VITE_WS=false; no socket to clean up
    }
  }, [conversationId, token, transcriptInitial]);

  useEffect(() => {
    if (!isWsEnabled || !conversationId || !token) return;

    cancelledRef.current = false;
    reconnectAttempts.current = 0;
    connect();

    return () => {
      cancelledRef.current = true;
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
      if (socketRef.current) {
        socketRef.current.close();
        socketRef.current = null;
      }
    };
  }, [conversationId, token, connect]);

  const sendMessage = (entry: TranscriptEntry) => {
    if (socketRef.current && socketRef.current.readyState === WebSocket.OPEN) {
      socketRef.current.send(JSON.stringify(entry));
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
