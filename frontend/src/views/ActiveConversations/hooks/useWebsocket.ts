import { useCallback, useEffect, useRef, useState } from "react";
import { TranscriptEntry } from "@/interfaces/transcript.interface";
import { useWebSocket } from "@/hooks/useWebSocket";
import {
  UseWebSocketTranscriptOptions,
  StatisticsPayload,
  TakeoverPayload,
} from "@/interfaces/websocket.interface";
import { isWsEnabled } from "@/config/api";

function toEpochMs(ct: string | number | undefined | null): number {
  if (ct == null) return 0;
  if (typeof ct === "number") return ct;
  const t = new Date(ct).getTime();
  return isNaN(t) ? 0 : t;
}

const EFFECTIVE_TOPICS = ["message", "statistics", "finalize", "takeover"];

export function useWebSocketTranscript({
  conversationId,
  token,
  transcriptInitial = [],
  lang = "en",
}: UseWebSocketTranscriptOptions) {
  const [messages, setMessages] = useState<TranscriptEntry[]>([]);
  const [statistics, setStatistics] = useState<StatisticsPayload>({});
  const [takeoverInfo, setTakeoverInfo] = useState<TakeoverPayload>({});
  const transcriptInitialRef = useRef(transcriptInitial);
  transcriptInitialRef.current = transcriptInitial;

  const handleMessage = useCallback((data: Record<string, unknown>) => {
    if ((data.topic === "message" || data.type === "message") && data.payload) {
      const newEntries = Array.isArray(data.payload)
        ? data.payload
        : [data.payload];

      setMessages((prev) => {
        const combined = [...prev];
        for (const entry of newEntries as TranscriptEntry[]) {
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
        ...(data.payload as StatisticsPayload),
      }));
    }

    if (data.topic === "takeover" || data.type === "takeover") {
      const payload = data.payload as { supervisor_id?: string; user_id?: string };
      setTakeoverInfo({
        supervisor_id: payload?.supervisor_id,
        user_id: payload?.user_id,
        timestamp: new Date().toISOString(),
      });
    }
  }, []);

  const { isConnected, send } = useWebSocket({
    roomType: "conversation",
    conversationId: conversationId || undefined,
    token,
    topics: EFFECTIVE_TOPICS,
    lang,
    onMessage: handleMessage,
    reconnect: false,
  });

  // Set initial messages when connected
  useEffect(() => {
    if (isConnected) {
      setMessages(transcriptInitialRef.current);
    }
  }, [isConnected]);

  const sendMessage = useCallback(
    (entry: TranscriptEntry) => {
      send(entry);
    },
    [send]
  );

  // When conversationId/token are empty (disabled), don't connect - return empty state
  const shouldConnect = isWsEnabled && !!conversationId && !!token;

  return {
    messages: shouldConnect ? messages : transcriptInitial,
    isConnected: shouldConnect ? isConnected : false,
    sendMessage,
    statistics,
    takeoverInfo,
  };
}
