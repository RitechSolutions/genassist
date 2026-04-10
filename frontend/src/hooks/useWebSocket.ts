import { useCallback, useEffect, useRef, useState } from "react";
import { getApiUrl, getWsUrl, getWsVersion, isWsEnabled } from "@/config/api";
import { getTenantId } from "@/services/auth";

export type WebSocketRoomType = "dashboard" | "conversation";

export interface UseWebSocketOptions {
  roomType: WebSocketRoomType;
  conversationId?: string;
  token: string;
  topics: string[];
  lang?: string;
  onMessage: (data: Record<string, unknown>) => void;
  /** Enable reconnect with backoff (used for dashboard). Default: true for dashboard, false for conversation */
  reconnect?: boolean;
  maxReconnectAttempts?: number;
}

export interface UseWebSocketReturn {
  isConnected: boolean;
  error: Error | null;
  refetch: () => void;
  send: (data: unknown) => void;
}

function buildWebSocketUrl(
  roomType: WebSocketRoomType,
  conversationId: string | undefined,
  token: string,
  topics: string[],
  lang: string,
  wsBaseUrl: string
): string {
  const wsVersion = getWsVersion();
  const topicsQuery = topics.map((t) => `topics=${t}`).join("&");
  const tenant = getTenantId();
  const tenantParam = tenant ? `&x-tenant-id=${tenant}` : "";
  const langParam = lang ? `&lang=${lang}` : "";

  if (roomType === "dashboard") {
    if (wsVersion === 1) {
      return `${wsBaseUrl}/conversations/ws/dashboard/list?access_token=${token}&${topicsQuery}${tenantParam}${langParam}`;
    }
    return `${wsBaseUrl}/ws/dashboard/list?access_token=${token}&${topicsQuery}${tenantParam}${langParam}`;
  }

  // conversation
  if (!conversationId) {
    throw new Error("conversationId is required for conversation room type");
  }
  if (wsVersion === 1) {
    return `${wsBaseUrl}/conversations/ws/${conversationId}?access_token=${token}&${topicsQuery}${tenantParam}${langParam}`;
  }
  return `${wsBaseUrl}/ws/conversations/${conversationId}?access_token=${token}&${topicsQuery}${tenantParam}${langParam}`;
}

export function useWebSocket({
  roomType,
  conversationId,
  token,
  topics,
  lang = "en",
  onMessage,
  reconnect: enableReconnect,
  maxReconnectAttempts = 5,
}: UseWebSocketOptions): UseWebSocketReturn {
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const socketRef = useRef<WebSocket | null>(null);
  const reconnectAttempts = useRef(0);
  const onMessageRef = useRef(onMessage);
  onMessageRef.current = onMessage;

  const connect = useCallback(() => {
    if (!isWsEnabled) return;
    if (!token) return;
    if (roomType === "conversation" && !conversationId) return;

    getWsUrl()
      .then(async (wsBaseUrl) => {
        if (!isWsEnabled || !token) return;
        if (roomType === "conversation" && !conversationId) return;

        let baseApiUrl = await getApiUrl();
        // replace http with ws
        baseApiUrl = baseApiUrl.replace("http", "ws");

        const wsUrl = buildWebSocketUrl(
          roomType,
          conversationId,
          token,
          topics,
          lang,
          wsBaseUrl || baseApiUrl
        )?.replace(/\/\//g, "/");

        const socket = new WebSocket(wsUrl);
        socketRef.current = socket;

        socket.onopen = () => {
          setIsConnected(true);
          setError(null);
          reconnectAttempts.current = 0;
        };

        socket.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data) as Record<string, unknown>;
            const topic = (data.topic ?? data.type) as string;

            // Handle ping from server (dashboard)
            if (data.type === "ping") {
              socket.send(JSON.stringify({ type: "pong" }));
              return;
            }

            onMessageRef.current(data);
          } catch {
            // ignore parse errors
          }
        };

        socket.onerror = () => {
          setError(new Error("WebSocket error"));
          setIsConnected(false);
        };

        socket.onclose = () => {
          setIsConnected(false);
          const shouldReconnect =
            enableReconnect !== false &&
            roomType === "dashboard" &&
            reconnectAttempts.current < maxReconnectAttempts;

          if (shouldReconnect) {
            reconnectAttempts.current++;
            const delay = Math.min(
              1000 * reconnectAttempts.current,
              10000
            );
            setTimeout(connect, delay);
          } else if (roomType === "dashboard" && reconnectAttempts.current >= maxReconnectAttempts) {
            setError(new Error("Failed to reconnect"));
          }
        };
      })
      .catch((e) => {
        setError(e instanceof Error ? e : new Error(String(e)));
      });
  }, [token, roomType, conversationId, topics, lang, enableReconnect, maxReconnectAttempts]);

  useEffect(() => {
    connect();
    return () => {
      if (socketRef.current) {
        socketRef.current.close();
        socketRef.current = null;
      }
    };
  }, [connect]);

  const refetch = useCallback(() => {
    if (socketRef.current?.readyState !== WebSocket.OPEN) {
      connect();
    }
  }, [connect]);

  const send = useCallback((data: unknown) => {
    if (socketRef.current?.readyState === WebSocket.OPEN) {
      socketRef.current.send(
        typeof data === "string" ? data : JSON.stringify(data)
      );
    }
  }, []);

  return { isConnected, error, refetch, send };
}
