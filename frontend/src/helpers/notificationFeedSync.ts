import type { QueryClient, InfiniteData } from "@tanstack/react-query"

import type { Notification } from "@/interfaces/notification.interface"
import {
  fetchDashboardNotificationsPage,
  type NotificationTypeFilter,
} from "@/services/dashboard"
import {
  NOTIFICATIONS_PAGE_SIZE,
  notificationsInfiniteQueryKey,
} from "@/constants/notificationFeed"
import type { NotificationUserSettings } from "@/services/notificationSettings"

type NotificationFeedPage = {
  items: Notification[]
  hasMore: boolean
}

export function buildNotificationFeedQueryKey(
  settings: NotificationUserSettings,
  typeFilter: NotificationTypeFilter = "all",
  levelFilter: "all" | "info" | "success" | "warning" | "error" = "all"
) {
  return [
    ...notificationsInfiniteQueryKey(
      settings.conversationStarted,
      typeFilter,
      levelFilter
    ),
    settings.conversationHostility,
    settings.conversationFinalizedHostility,
    settings.workflowFailed,
  ] as const
}

/** Fetch first page from API and apply to the react-query infinite cache (dashboard WS resync). */
export async function syncNotificationFeedFromApi(
  queryClient: QueryClient,
  queryKey: readonly unknown[],
  settings: NotificationUserSettings,
  typeFilter: NotificationTypeFilter = "all",
  levelFilter: "all" | "info" | "success" | "warning" | "error" = "all"
): Promise<void> {
  const page = await fetchDashboardNotificationsPage(
    NOTIFICATIONS_PAGE_SIZE,
    0,
    settings.conversationStarted,
    settings.conversationHostility,
    settings.conversationFinalizedHostility,
    settings.workflowFailed,
    typeFilter,
    levelFilter
  )
  if (!page) return

  queryClient.setQueryData<InfiniteData<NotificationFeedPage>>(queryKey, {
    pages: [{ items: page.items, hasMore: page.hasMore }],
    pageParams: [0],
  })
}
