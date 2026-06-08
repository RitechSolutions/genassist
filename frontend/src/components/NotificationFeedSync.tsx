import { useEffect } from "react"
import { useQueryClient } from "@tanstack/react-query"

import { useWebSocketDashboardContext } from "@/context/WebSocketDashboardContext"
import {
  buildNotificationFeedQueryKey,
  syncNotificationFeedFromApi,
} from "@/helpers/notificationFeedSync"
import {
  NOTIFICATIONS_INFINITE_QUERY_KEY,
} from "@/hooks/useNotifications"
import {
  DEFAULT_NOTIFICATION_USER_SETTINGS,
  useNotificationUserSettings,
} from "@/hooks/useNotificationUserSettings"

/**
 * Keeps notification feeds in sync when the dashboard WS emits `notification`.
 * Mirrors ActiveConversations resync → fetchDashboardConversations on resyncHint.
 */
export function NotificationFeedSync() {
  const queryClient = useQueryClient()
  const { notificationResyncHint } = useWebSocketDashboardContext()
  const { settings } = useNotificationUserSettings()
  const effectiveSettings = settings ?? DEFAULT_NOTIFICATION_USER_SETTINGS

  useEffect(() => {
    if (notificationResyncHint === 0) return

    let cancelled = false

    const sync = async () => {
      const defaultKey = buildNotificationFeedQueryKey(effectiveSettings, "all", "all")
      await syncNotificationFeedFromApi(
        queryClient,
        defaultKey,
        effectiveSettings,
        "all",
        "all"
      )
      if (cancelled) return
      void queryClient.invalidateQueries({
        queryKey: NOTIFICATIONS_INFINITE_QUERY_KEY,
      })
    }

    void sync()

    return () => {
      cancelled = true
    }
  }, [notificationResyncHint, effectiveSettings, queryClient])

  return null
}
