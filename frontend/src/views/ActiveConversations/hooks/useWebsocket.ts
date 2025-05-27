import { useEffect, useRef, useState } from "react";
import { TranscriptEntry } from "@/interfaces/transcript.interface";

interface UseWebSocketTranscriptOptions {
  conversationId: string;
  token: string;
  baseUrl: string;
  port: string;
  transcriptInitial?: TranscriptEntry[];
}

interface StatisticsPayload {
  in_progress_hostility_score?: number;
  topic?: string;
  sentiment?: string;
  [key: string]: number | string | undefined;
}

export function useWebSocketTranscript({
  conversationId,
  token,
  baseUrl,
  port,
  transcriptInitial = [],
}: UseWebSocketTranscriptOptions) {
  const [messages, setMessages] = useState<TranscriptEntry[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [statistics, setStatistics] = useState<StatisticsPayload>({});
  const socketRef = useRef<WebSocket | null>(null);
  const lastConversationIdRef = useRef<string | null>(null);

  useEffect(() => {
    if (!conversationId || !token) return;

    if (lastConversationIdRef.current === conversationId) return;

    lastConversationIdRef.current = conversationId;

    const topics = ["message", "statistics", "finalize", "takeover"];
    const queryString = topics.map((t) => `topics=${t}`).join("&");
    const wsUrl = `wss://${baseUrl}:${port}/api/conversations/ws/${conversationId}?access_token=${token}&lang=en&${queryString}`;
    console.log("Connecting to WebSocket:", wsUrl);

    const socket = new WebSocket(wsUrl);
    socketRef.current = socket;

    socket.onopen = () => {
      console.log("WebSocket connected");
      setIsConnected(true);
      setMessages(transcriptInitial);
    };

    socket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        console.log("Incoming WebSocket message:", data);
    
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
          console.log("Received statistics:", data.payload);
          setStatistics(prev => ({
            ...prev,
            ...data.payload
          }));
        }
      } catch (e) {
        console.error("JSON parse error", e);
      }
    };

    socket.onerror = (err) => {
      console.error("WebSocket error", err);
    };

    socket.onclose = () => {
      console.log("WebSocket disconnected");
      setIsConnected(false);
      lastConversationIdRef.current = null;
    };

    return () => {
      socket.close();
    };
  }, [conversationId, token, baseUrl, port, transcriptInitial]);

  const sendMessage = (entry: TranscriptEntry) => {
    if (socketRef.current && socketRef.current.readyState === WebSocket.OPEN) {
      socketRef.current.send(JSON.stringify(entry));
    } else {
      console.warn("⚠️ Cannot send message: WebSocket not open");
    }
  };

  return {
    messages,
    isConnected,
    sendMessage,
    statistics
  };
}
