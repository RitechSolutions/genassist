import { useWebSocketDashboardContext } from "@/context/WebSocketDashboardContext";

/**
 * Hook for dashboard WebSocket data. Uses the shared WebSocketDashboardContext
 * which maintains a stable connection across Dashboard and Transcripts pages.
 */
export function useWebSocketDashboard() {
  return useWebSocketDashboardContext();
}
