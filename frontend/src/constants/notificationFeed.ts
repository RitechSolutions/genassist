import type { NotificationTypeFilter } from "@/services/dashboard"

export const NOTIFICATIONS_INFINITE_QUERY_KEY = [
  "notifications-feed-infinite",
] as const

export const NOTIFICATIONS_PAGE_SIZE = 10

export function notificationsInfiniteQueryKey(
  conversationStarted: boolean,
  notificationType: NotificationTypeFilter = "all",
  notificationLevel: "all" | "info" | "success" | "warning" | "error" = "all"
): readonly [
  string,
  boolean,
  NotificationTypeFilter,
  "all" | "info" | "success" | "warning" | "error",
] {
  return [
    NOTIFICATIONS_INFINITE_QUERY_KEY[0],
    conversationStarted,
    notificationType,
    notificationLevel,
  ]
}
