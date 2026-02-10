import { useEffect, useRef, useState } from "react";
import { TranscriptEntry } from "@/interfaces/transcript.interface";
import { getWsUrl, isWsEnabled } from "@/config/api";
import { UseWebSocketTranscriptOptions, StatisticsPayload, TakeoverPayload } from "@/interfaces/websocket.interface";
import { getTenantId } from "@/services/auth";

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
  const lastConversationIdRef = useRef<string | null>(null);

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

    getWsUrl()
      .then((wsBaseUrl) => {
        if (cancelled || !isWsEnabled) return;
        const wsUrl = `${wsBaseUrl}/conversations/ws/${conversationId}?access_token=${token}&lang=en&${queryString}${tenantParam}`;

        socket = new WebSocket(wsUrl);
        socketRef.current = socket;

        socket.onopen = () => {
          if (!cancelled) {
            setIsConnected(true);
            setMessages(transcriptInitial);
          }
        };

        socket.onmessage = (event) => {
          if (cancelled) return;
          try {
            const data = JSON.parse(event.data);

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
                      msg.create_time === entry.create_time
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

        socket.onerror = () => {
          // ignore
        };

        socket.onclose = () => {
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
  }, [conversationId, token, transcriptInitial]);

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