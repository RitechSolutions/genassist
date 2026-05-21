import type { NotificationTypeFilter } from "@/services/dashboard"

export const NOTIFICATION_BELL_QUERY_KEY = ["notifications-bell"] as const
export const NOTIFICATIONS_INFINITE_QUERY_KEY = [
  "notifications-feed-infinite",
] as const

export function notificationsInfiniteQueryKey(
  conversationStarted: boolean,
  notificationType: NotificationTypeFilter = "all",
  unreadOnly = false
): readonly [string, boolean, NotificationTypeFilter, boolean] {
  return [
    NOTIFICATIONS_INFINITE_QUERY_KEY[0],
    conversationStarted,
    notificationType,
    unreadOnly,
  ]
}
