import type { QueryClient, InfiniteData } from "@tanstack/react-query"

import { Notification } from "@/interfaces/notification.interface"
import type { NotificationTypeFilter } from "@/services/dashboard"
import {
  isConversationFinalizedHostilityNotification,
  isConversationHostilityNotification,
  isConversationStartedNotification,
  isWorkflowFailedNotification,
} from "@/hooks/useNotificationUserSettings"
import {
  NOTIFICATION_BELL_QUERY_KEY,
  NOTIFICATIONS_INFINITE_QUERY_KEY,
} from "@/constants/notificationQueryKeys"

export type NotificationFeedIncludes = {
  conversationStarted: boolean
  conversationHostility: boolean
  conversationFinalizedHostility: boolean
  workflowFailed: boolean
}

type NotificationFeedPage = {
  items: Notification[]
  hasMore: boolean
}

export function mapSocketPayloadToNotification(
  payload: Record<string, unknown>
): Notification | null {
  const id = String(payload.id ?? "")
  if (!id) return null
  const level = String(payload.type ?? "info")
  const type: Notification["type"] =
    level === "success" ||
    level === "warning" ||
    level === "error" ||
    level === "info"
      ? level
      : "info"
  return {
    id,
    title: String(payload.title ?? "Notification"),
    description: String(payload.description ?? ""),
    timestamp: String(payload.timestamp ?? new Date().toISOString()),
    type,
    actionUrl: payload.action_url ? String(payload.action_url) : undefined,
    read: false,
  }
}

export function notificationAllowedByUserSettings(
  notificationId: string,
  includes: NotificationFeedIncludes
): boolean {
  if (
    isConversationStartedNotification(notificationId) &&
    !includes.conversationStarted
  ) {
    return false
  }
  if (
    isConversationHostilityNotification(notificationId) &&
    !includes.conversationHostility
  ) {
    return false
  }
  if (
    isConversationFinalizedHostilityNotification(notificationId) &&
    !includes.conversationFinalizedHostility
  ) {
    return false
  }
  if (isWorkflowFailedNotification(notificationId) && !includes.workflowFailed) {
    return false
  }
  return true
}

function notificationMatchesTypeFilter(
  notificationId: string,
  typeFilter: NotificationTypeFilter
): boolean {
  if (typeFilter === "all") return true
  if (typeFilter === "conversation_started") {
    return isConversationStartedNotification(notificationId)
  }
  if (typeFilter === "conversation_hostility") {
    return isConversationHostilityNotification(notificationId)
  }
  if (typeFilter === "conversation_finalized_hostility") {
    return isConversationFinalizedHostilityNotification(notificationId)
  }
  return false
}

function upsertNotificationList(
  items: Notification[],
  incoming: Notification
): Notification[] {
  const withoutDup = items.filter((item) => item.id !== incoming.id)
  return [incoming, ...withoutDup]
}

export function applyIncomingNotificationToCaches(
  queryClient: QueryClient,
  incoming: Notification,
  includes: NotificationFeedIncludes
): void {
  if (!notificationAllowedByUserSettings(incoming.id, includes)) return

  queryClient.setQueriesData<{
    items: Notification[]
    unreadCount: number
  }>(
    { queryKey: NOTIFICATION_BELL_QUERY_KEY },
    (prev) => {
      if (!prev) return prev
      const existing = prev.items.find((n) => n.id === incoming.id)
      const items = upsertNotificationList(prev.items, incoming).slice(
        0,
        10
      )
      let unreadCount = prev.unreadCount
      if (!existing && !incoming.read) {
        unreadCount += 1
      } else if (existing?.read && !incoming.read) {
        unreadCount += 1
      } else if (existing && !existing.read && incoming.read) {
        unreadCount = Math.max(0, unreadCount - 1)
      }
      return {
        items,
        unreadCount,
      }
    }
  )

  queryClient.setQueriesData<InfiniteData<NotificationFeedPage>>(
    { queryKey: NOTIFICATIONS_INFINITE_QUERY_KEY },
    (old, { queryKey }) => {
      if (!old?.pages?.length) return old

      const key = queryKey as readonly unknown[]
      const typeFilter = (key[2] as NotificationTypeFilter) ?? "all"
      const unreadOnly = Boolean(key[3])

      if (!notificationMatchesTypeFilter(incoming.id, typeFilter)) {
        return old
      }
      if (unreadOnly && incoming.read) {
        return old
      }

      const pages = [...old.pages]
      const first = pages[0]
      const mergedItems = upsertNotificationList(first.items, incoming)
      pages[0] = { ...first, items: mergedItems }
      return { ...old, pages }
    }
  )
}

export function invalidateNotificationFeeds(queryClient: QueryClient): void {
  void queryClient.invalidateQueries({ queryKey: NOTIFICATION_BELL_QUERY_KEY })
  void queryClient.invalidateQueries({
    queryKey: NOTIFICATIONS_INFINITE_QUERY_KEY,
  })
}

export function handleDashboardNotificationMessage(
  queryClient: QueryClient,
  data: Record<string, unknown>,
  includes: NotificationFeedIncludes
): boolean {
  const topic = String(data.type ?? data.topic ?? "")
  if (topic !== "notification") return false

  const payload = (data.payload ?? {}) as Record<string, unknown>
  const incoming = mapSocketPayloadToNotification(payload)
  if (!incoming) return false

  applyIncomingNotificationToCaches(queryClient, incoming, includes)
  invalidateNotificationFeeds(queryClient)
  return true
}
