import { useCallback, useEffect, useRef, useState } from "react";
import { createWebSocket, createWebSocketDiagnostic } from "../utils/websocket";

export type ConnectionState = "connecting" | "connected" | "disconnected";

export interface UseChatWebSocketOptions {
  baseUrl: string;
  websocketUrl?: string;
  apiKey: string;
  tenant?: string;
  conversationId: string | null;
  guestToken: string | null;
  useWs: boolean;
  language?: string;
  /** Called when raw WebSocket message is received (parsed JSON) */
  onMessage: (data: Record<string, unknown>) => void;
  onConnectionState?: (state: ConnectionState) => void;
  /** Enable reconnect with backoff when connection drops. Default: true */
  reconnect?: boolean;
  maxReconnectAttempts?: number;
  reconnectBaseDelayMs?: number;
}

const DEFAULT_MAX_RECONNECT_ATTEMPTS = 5;
const DEFAULT_RECONNECT_BASE_DELAY_MS = 1000;

function buildChatWebSocketUrl(
  baseUrl: string,
  websocketUrl: string | undefined,
  conversationId: string,
  authParam: string,
  tenant: string | undefined,
  language: string
): string {
  const topics = ["message", "takeover", "finalize"];
  const topicsQuery = topics.map((t) => `topics=${t}`).join("&");
  const langParam = language ? `&lang=${language}` : "&lang=en";
  const tenantParam = tenant ? `&x-tenant-id=${encodeURIComponent(tenant)}` : "";

  // new websocket service
  if (websocketUrl) {
    return `${websocketUrl}/ws/conversations/${conversationId}?${authParam}${langParam}&${topicsQuery}${tenantParam}`;
  }

  // legacy websocket service
  const wsBase = baseUrl.replace("http", "ws");
  return `${wsBase}/api/conversations/ws/${conversationId}?${authParam}${langParam}&${topicsQuery}${tenantParam}`;
}

/**
 * Unified WebSocket hook for chat conversations.
 * Handles connection lifecycle, ping/pong keep-alive, and automatic reconnection.
 */
export function useChatWebSocket({
  baseUrl,
  websocketUrl,
  apiKey,
  tenant,
  conversationId,
  guestToken,
  useWs,
  language = "en",
  onMessage,
  onConnectionState,
  reconnect = true,
  maxReconnectAttempts = DEFAULT_MAX_RECONNECT_ATTEMPTS,
  reconnectBaseDelayMs = DEFAULT_RECONNECT_BASE_DELAY_MS,
}: UseChatWebSocketOptions): {
  connectionState: ConnectionState;
  connect: () => void;
  disconnect: () => void;
} {
  const [connectionState, setConnectionState] =
    useState<ConnectionState>("disconnected");
  const socketRef = useRef<WebSocket | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const onMessageRef = useRef(onMessage);
  const onConnectionStateRef = useRef(onConnectionState);

  onMessageRef.current = onMessage;
  onConnectionStateRef.current = onConnectionState;

  const updateConnectionState = useCallback(
    (state: ConnectionState) => {
      setConnectionState(state);
      onConnectionStateRef.current?.(state);
    },
    []
  );

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    reconnectAttemptsRef.current = 0;
    if (socketRef.current) {
      socketRef.current.close();
      socketRef.current = null;
    }
    updateConnectionState("disconnected");
  }, [updateConnectionState]);

  const connect = useCallback(() => {
    if (!useWs || !conversationId) {
      return;
    }

    // Close existing connection
    if (socketRef.current) {
      socketRef.current.close();
      socketRef.current = null;
    }

    const authParam = guestToken
      ? `access_token=${encodeURIComponent(guestToken)}`
      : `api_key=${encodeURIComponent(apiKey)}`;

    const wsUrl = buildChatWebSocketUrl(
      baseUrl,
      websocketUrl,
      conversationId,
      authParam,
      tenant,
      language
    );

    updateConnectionState("connecting");
    const socket = createWebSocket(wsUrl);
    socketRef.current = socket;

    socket.onopen = () => {
      reconnectAttemptsRef.current = 0;
      updateConnectionState("connected");
    };

    socket.onmessage = (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data as string) as Record<string, unknown>;

        // Respond to server-side heartbeat pings (keep connection active)
        if (data.type === "ping") {
          if (socketRef.current?.readyState === WebSocket.OPEN) {
            socketRef.current.send(JSON.stringify({ type: "pong" }));
          }
          return;
        }

        onMessageRef.current(data);
      } catch {
        // ignore parse errors
      }
    };

    socket.onerror = (error: Event) => {
      updateConnectionState("disconnected");
      const diagnostic = createWebSocketDiagnostic(error, wsUrl);
      console.error(`[GenAssist Chat] ${diagnostic}`);
    };

    socket.onclose = (event: CloseEvent) => {
      socketRef.current = null;
      updateConnectionState("disconnected");

      if (!event.wasClean) {
        const diagnostic = createWebSocketDiagnostic(event, wsUrl);
        console.warn(`[GenAssist Chat] ${diagnostic}`);
      }

      // Reconnect with backoff when connection drops unexpectedly
      const shouldReconnect =
        reconnect &&
        !event.wasClean &&
        reconnectAttemptsRef.current < maxReconnectAttempts;

      if (shouldReconnect) {
        reconnectAttemptsRef.current += 1;
        const delay = Math.min(
          reconnectBaseDelayMs * Math.pow(2, reconnectAttemptsRef.current - 1),
          30000
        );
        reconnectTimeoutRef.current = setTimeout(() => {
          reconnectTimeoutRef.current = null;
          connect();
        }, delay);
      }
    };
  }, [
    baseUrl,
    websocketUrl,
    apiKey,
    tenant,
    conversationId,
    guestToken,
    useWs,
    language,
    reconnect,
    maxReconnectAttempts,
    reconnectBaseDelayMs,
    updateConnectionState,
  ]);

  // Connect when conversationId is available, disconnect when it changes or is cleared
  useEffect(() => {
    if (useWs && conversationId) {
      connect();
    } else {
      disconnect();
    }
    return disconnect;
  }, [useWs, conversationId, connect, disconnect]);

  return { connectionState, connect, disconnect };
}
