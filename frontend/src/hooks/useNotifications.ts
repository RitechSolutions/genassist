import { useCallback, useEffect, useMemo, useRef } from "react"
import {
  useQuery,
  useQueryClient,
  useInfiniteQuery,
  useMutation,
  type InfiniteData,
} from "@tanstack/react-query"
import { toast } from "react-hot-toast"

import { isPollEnabled, isWsEnabled } from "@/config/api"
import { Notification } from "@/interfaces/notification.interface"
import {
  fetchDashboardNotificationsPage,
  fetchNotificationBellPreview,
  NOTIFICATIONS_PAGE_SIZE,
  type NotificationTypeFilter,
} from "@/services/dashboard"
import { markNotificationsRead } from "@/services/notificationReads"
import {
  NOTIFICATION_BELL_QUERY_KEY,
  NOTIFICATIONS_INFINITE_QUERY_KEY,
  notificationsInfiniteQueryKey,
} from "@/constants/notificationQueryKeys"
import { useNotificationUserSettings } from "@/hooks/useNotificationUserSettings"

export {
  NOTIFICATION_BELL_QUERY_KEY,
  NOTIFICATIONS_INFINITE_QUERY_KEY,
  notificationsInfiniteQueryKey,
} from "@/constants/notificationQueryKeys"

const LEGACY_READ_MAP_KEY = "notifications_read_map"
const LEGACY_READ_MAP_MIGRATED_KEY = "notifications_read_map_migrated_v1"

type NotificationFeedPage = {
  items: Notification[]
  hasMore: boolean
}

function loadLegacyReadMap(): Record<string, boolean> {
  try {
    const raw = localStorage.getItem(LEGACY_READ_MAP_KEY)
    if (!raw) return {}
    return JSON.parse(raw) as Record<string, boolean>
  } catch {
    return {}
  }
}

async function migrateLegacyReadMapOnce(): Promise<void> {
  if (localStorage.getItem(LEGACY_READ_MAP_MIGRATED_KEY)) return
  const readMap = loadLegacyReadMap()
  const ids = Object.keys(readMap).filter((id) => readMap[id])
  if (ids.length > 0) {
    await markNotificationsRead(ids)
  }
  localStorage.removeItem(LEGACY_READ_MAP_KEY)
  localStorage.setItem(LEGACY_READ_MAP_MIGRATED_KEY, "1")
}

function useNotificationFeedIncludes() {
  const { settings } = useNotificationUserSettings()
  return useMemo(
    () => ({
      conversationStarted: settings.conversationStarted,
      conversationHostility: settings.conversationHostility,
      conversationFinalizedHostility: settings.conversationFinalizedHostility,
      workflowFailed: settings.workflowFailed,
    }),
    [settings]
  )
}

export function useInvalidateNotificationQueries() {
  const queryClient = useQueryClient()
  return useCallback(() => {
    void queryClient.invalidateQueries({ queryKey: NOTIFICATION_BELL_QUERY_KEY })
    void queryClient.invalidateQueries({
      queryKey: NOTIFICATIONS_INFINITE_QUERY_KEY,
    })
  }, [queryClient])
}

function useMarkNotificationsReadMutation() {
  const invalidateFeeds = useInvalidateNotificationQueries()

  return useMutation({
    mutationFn: (notificationIds: string[]) => markNotificationsRead(notificationIds),
    onSuccess: invalidateFeeds,
    onError: invalidateFeeds,
  })
}

/** Bell popover: latest 10 notifications from dedicated endpoint. */
export const useNotificationBell = () => {
  const markReadMutation = useMarkNotificationsReadMutation()
  const legacyMigrationStarted = useRef(false)
  const includes = useNotificationFeedIncludes()

  const feedIncludes = useMemo(
    () => ({
      includeConversationStarted: includes.conversationStarted,
      includeConversationHostility: includes.conversationHostility,
      includeConversationFinalizedHostility: includes.conversationFinalizedHostility,
      includeWorkflowFailed: includes.workflowFailed,
    }),
    [includes]
  )

  const bellQueryKey = [...NOTIFICATION_BELL_QUERY_KEY, feedIncludes] as const

  const { data, refetch } = useQuery({
    queryKey: bellQueryKey,
    queryFn: async () => {
      const preview = await fetchNotificationBellPreview(feedIncludes)
      return preview ?? { items: [], unreadCount: 0 }
    },
    // Poll as fallback when WS is enabled (isPollEnabled is false then) so the bell still updates if the dashboard socket misses an event.
    refetchInterval: isPollEnabled ? 15000 : isWsEnabled ? 30000 : false,
  })

  useEffect(() => {
    if (legacyMigrationStarted.current) return
    legacyMigrationStarted.current = true
    void migrateLegacyReadMapOnce().then(() => {
      void refetch()
    })
  }, [refetch])

  useEffect(() => {
    void refetch()
  }, [feedIncludes, refetch])

  const queryClient = useQueryClient()

  const markAsRead = useCallback(
    (id: string) => {
      queryClient.setQueryData<{
        items: Notification[]
        unreadCount: number
      }>(bellQueryKey, (prev) => {
        if (!prev) return prev
        const wasUnread = prev.items.some((n) => n.id === id && !n.read)
        return {
          items: prev.items.map((n) =>
            n.id === id ? { ...n, read: true } : n
          ),
          unreadCount: wasUnread
            ? Math.max(0, prev.unreadCount - 1)
            : prev.unreadCount,
        }
      })
      markReadMutation.mutate([id])
    },
    [queryClient, bellQueryKey, markReadMutation]
  )

  return {
    notifications: data?.items ?? [],
    unreadCount: data?.unreadCount ?? 0,
    markAsRead,
    refetch,
  }
}

/** Notifications page: infinite scroll */
export const useNotificationsInfinite = ({
  typeFilter = "all",
  unreadOnly = false,
}: {
  typeFilter?: NotificationTypeFilter
  unreadOnly?: boolean
} = {}) => {
  const queryClient = useQueryClient()
  const markReadMutation = useMarkNotificationsReadMutation()
  const legacyMigrationStarted = useRef(false)
  const includes = useNotificationFeedIncludes()

  const feedIncludes = useMemo(
    () => ({
      includeConversationStarted: includes.conversationStarted,
      includeConversationHostility: includes.conversationHostility,
      includeConversationFinalizedHostility: includes.conversationFinalizedHostility,
      includeWorkflowFailed: includes.workflowFailed,
    }),
    [includes]
  )

  const infiniteKey = [
    ...notificationsInfiniteQueryKey(
      includes.conversationStarted,
      typeFilter,
      unreadOnly
    ),
    includes.conversationHostility,
    includes.conversationFinalizedHostility,
    includes.workflowFailed,
  ] as const

  const {
    data,
    hasNextPage,
    fetchNextPage,
    isFetchingNextPage,
    isPending,
    isError,
    refetch: refetchInfinite,
  } = useInfiniteQuery({
    queryKey: infiniteKey,
    queryFn: async ({ pageParam }): Promise<NotificationFeedPage> => {
      const skip = pageParam as number
      const page = await fetchDashboardNotificationsPage(
        NOTIFICATIONS_PAGE_SIZE,
        skip,
        feedIncludes,
        typeFilter,
        unreadOnly
      )
      if (!page) return { items: [], hasMore: false }
      return {
        items: page.items,
        hasMore: page.hasMore,
      }
    },
    initialPageParam: 0,
    getNextPageParam: (lastPage, _pages, lastSkip) =>
      lastPage.hasMore ? (lastSkip as number) + lastPage.items.length : undefined,
  })

  useEffect(() => {
    if (legacyMigrationStarted.current) return
    legacyMigrationStarted.current = true
    void migrateLegacyReadMapOnce().then(() => {
      void refetchInfinite()
    })
  }, [refetchInfinite])

  const flatNotifications = useMemo(
    () => data?.pages.flatMap((p) => p.items) ?? [],
    [data]
  )

  const setInfinitePagesRead = useCallback(
    (predicate: (n: Notification) => boolean) => {
      queryClient.setQueryData<InfiniteData<NotificationFeedPage>>(
        infiniteKey,
        (old) => {
          if (!old) return old
          return {
            ...old,
            pages: old.pages.map((page) => ({
              ...page,
              items: page.items.map((n) =>
                predicate(n) ? { ...n, read: true } : n
              ),
            })),
          }
        }
      )
    },
    [queryClient, infiniteKey]
  )

  const persistMarkRead = useCallback(
    (ids: string[]) => {
      if (ids.length === 0) return
      markReadMutation.mutate(ids)
    },
    [markReadMutation]
  )

  const markAsRead = useCallback(
    (id: string) => {
      if (unreadOnly) {
        queryClient.setQueryData<InfiniteData<NotificationFeedPage>>(
          infiniteKey,
          (old) => {
            if (!old) return old
            return {
              ...old,
              pages: old.pages.map((page) => ({
                ...page,
                items: page.items.filter((n) => n.id !== id),
              })),
            }
          }
        )
      } else {
        setInfinitePagesRead((n) => n.id === id)
      }
      persistMarkRead([id])
    },
    [unreadOnly, queryClient, infiniteKey, setInfinitePagesRead, persistMarkRead]
  )

  const markAllAsRead = useCallback(() => {
    const unreadIds = flatNotifications
      .filter((n) => !n.read)
      .map((n) => n.id)
    if (unreadIds.length === 0) return
    if (unreadOnly) {
      queryClient.setQueryData<InfiniteData<NotificationFeedPage>>(
        infiniteKey,
        (old) => {
          if (!old) return old
          return {
            ...old,
            pages: old.pages.map(() => ({ items: [], hasMore: false })),
          }
        }
      )
    } else {
      setInfinitePagesRead(() => true)
    }
    persistMarkRead(unreadIds)
    toast.success("All loaded notifications are marked as read.")
  }, [
    flatNotifications,
    unreadOnly,
    queryClient,
    infiniteKey,
    setInfinitePagesRead,
    persistMarkRead,
  ])

  return {
    notifications: flatNotifications,
    hasNextPage,
    fetchNextPage,
    isFetchingNextPage,
    isLoading: isPending,
    isError,
    refetch: refetchInfinite,
    markAsRead,
    markAllAsRead,
  }
}
