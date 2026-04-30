import { useCallback, useEffect, useMemo } from "react"
import {
  useQuery,
  useQueryClient,
  useInfiniteQuery,
  type InfiniteData,
} from "@tanstack/react-query"
import { toast } from "react-hot-toast"

import { isPollEnabled } from "@/config/api"
import { Notification } from "@/interfaces/notification.interface"
import {
  fetchDashboardNotifications,
  fetchDashboardNotificationsPage,
  type NotificationTypeFilter,
} from "@/services/dashboard"
import { useWebSocket } from "@/hooks/useWebSocket"
import {
  isConversationStartedNotification,
  useNotificationPreferences,
} from "@/hooks/useNotificationPreferences"

export const NOTIFICATIONS_QUERY_KEY = ["notifications-feed"] as const
export const NOTIFICATIONS_INFINITE_QUERY_KEY = [
  "notifications-feed-infinite",
] as const

export function notificationsInfiniteQueryKey(
  conversationStarted: boolean,
  notificationType: NotificationTypeFilter = "all"
): readonly [string, boolean, NotificationTypeFilter] {
  return [NOTIFICATIONS_INFINITE_QUERY_KEY[0], conversationStarted, notificationType]
}

const NOTIFICATION_READ_MAP_KEY = "notifications_read_map"
const NOTIFICATIONS_PAGE_SIZE = 20

type NotificationFeedPage = {
  items: Notification[]
  hasMore: boolean
}

function loadReadMap(): Record<string, boolean> {
  try {
    const raw = localStorage.getItem(NOTIFICATION_READ_MAP_KEY)
    if (!raw) return {}
    return JSON.parse(raw) as Record<string, boolean>
  } catch {
    return {}
  }
}

function saveReadMap(readMap: Record<string, boolean>): void {
  localStorage.setItem(NOTIFICATION_READ_MAP_KEY, JSON.stringify(readMap))
}

function applyReadMap(items: Notification[]): Notification[] {
  const readMap = loadReadMap()
  return items.map((item) => ({ ...item, read: Boolean(readMap[item.id]) }))
}

export const useNotifications = () => {
  const queryClient = useQueryClient()
  const { preferences } = useNotificationPreferences()

  const { data: notifications = [], refetch } = useQuery<Notification[]>({
    queryKey: [...NOTIFICATIONS_QUERY_KEY, preferences.conversationStarted],
    queryFn: async () => {
      const items = await fetchDashboardNotifications(80, {
        includeConversationStarted: preferences.conversationStarted,
      })
      return applyReadMap(items ?? [])
    },
    refetchInterval: isPollEnabled ? 15000 : false,
  })

  const updateCachedNotifications = useCallback(
    (updater: (prev: Notification[]) => Notification[]) => {
      queryClient.setQueryData<Notification[]>(
        [...NOTIFICATIONS_QUERY_KEY, preferences.conversationStarted],
        (prev) => updater(prev ?? [])
      )
    },
    [queryClient, preferences.conversationStarted]
  )

  const markAllAsRead = () => {
    const readMap = loadReadMap()
    notifications.forEach((notification) => {
      readMap[notification.id] = true
    })
    saveReadMap(readMap)
    updateCachedNotifications((prev) =>
      prev.map((notification) => ({ ...notification, read: true }))
    )
    toast.success("All notifications are marked as read.")
  }

  const markAsRead = (id: string) => {
    const readMap = loadReadMap()
    readMap[id] = true
    saveReadMap(readMap)
    updateCachedNotifications((prev) =>
      prev.map((notification) =>
        notification.id === id ? { ...notification, read: true } : notification
      )
    )
  }

  const handleSocketMessage = useCallback(
    (data: Record<string, unknown>) => {
      const topic = String(data.type ?? data.topic ?? "")
      if (topic !== "notification") return
      const payload = (data.payload ?? {}) as Record<string, unknown>
      const incoming: Notification = {
        id: String(payload.id ?? ""),
        title: String(payload.title ?? "Notification"),
        description: String(payload.description ?? ""),
        timestamp: String(payload.timestamp ?? new Date().toISOString()),
        type: (payload.type as Notification["type"]) ?? "info",
        actionUrl: payload.action_url ? String(payload.action_url) : undefined,
        read: Boolean(loadReadMap()[String(payload.id ?? "")]),
      }

      if (!incoming.id) return
      if (
        !preferences.conversationStarted &&
        isConversationStartedNotification(incoming.id)
      ) {
        return
      }

      updateCachedNotifications((prev) => {
        const exists = prev.some((item) => item.id === incoming.id)
        if (exists) {
          return prev.map((item) =>
            item.id === incoming.id ? { ...item, ...incoming } : item
          )
        }
        return [incoming, ...prev]
      })

      void queryClient.invalidateQueries({
        queryKey: NOTIFICATIONS_INFINITE_QUERY_KEY,
      })
    },
    [
      preferences.conversationStarted,
      updateCachedNotifications,
      queryClient,
    ]
  )

  useWebSocket({
    roomType: "dashboard",
    token: localStorage.getItem("access_token") || "",
    topics: ["notification"],
    onMessage: handleSocketMessage,
    reconnect: true,
    maxReconnectAttempts: 5,
  })

  useEffect(() => {
    void refetch()
  }, [preferences.conversationStarted, refetch])

  const unreadCount = useMemo(
    () => notifications.filter((notification) => !notification.read).length,
    [notifications]
  )

  return {
    notifications,
    unreadCount,
    markAllAsRead,
    markAsRead,
    refetch,
  }
}

export const useNotificationsInfinite = ({
  typeFilter = "all",
}: {
  typeFilter?: NotificationTypeFilter
} = {}) => {
  const queryClient = useQueryClient()
  const { preferences } = useNotificationPreferences()
  const conversationStarted = preferences.conversationStarted
  const infiniteKey = notificationsInfiniteQueryKey(conversationStarted, typeFilter)

  const infinite = useInfiniteQuery({
    queryKey: infiniteKey,
    queryFn: async ({ pageParam }): Promise<NotificationFeedPage> => {
      const skip = pageParam as number
      const page = await fetchDashboardNotificationsPage(
        NOTIFICATIONS_PAGE_SIZE,
        skip,
        conversationStarted,
        typeFilter
      )
      if (!page) return { items: [], hasMore: false }
      return {
        items: applyReadMap(page.items),
        hasMore: page.hasMore,
      }
    },
    initialPageParam: 0,
    getNextPageParam: (lastPage, _pages, lastSkip) =>
      lastPage.hasMore ? (lastSkip as number) + lastPage.items.length : undefined,
  })

  const flatNotifications = useMemo(
    () => infinite.data?.pages.flatMap((p) => p.items) ?? [],
    [infinite.data]
  )

  const setInfinitePagesRead = useCallback(
    (predicate: (n: Notification) => boolean) => {
      queryClient.setQueryData<InfiniteData<NotificationFeedPage>>(
        notificationsInfiniteQueryKey(conversationStarted),
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
    [queryClient, conversationStarted, typeFilter]
  )

  const markAsRead = useCallback(
    (id: string) => {
      const readMap = loadReadMap()
      readMap[id] = true
      saveReadMap(readMap)
      setInfinitePagesRead((n) => n.id === id)
      void queryClient.invalidateQueries({
        queryKey: [...NOTIFICATIONS_QUERY_KEY, conversationStarted],
      })
    },
    [queryClient, conversationStarted, setInfinitePagesRead]
  )

  const markAllAsRead = useCallback(() => {
    const key = notificationsInfiniteQueryKey(conversationStarted, typeFilter)
    const pages = queryClient.getQueryData<InfiniteData<NotificationFeedPage>>(
      key
    )
    const ids = pages?.pages.flatMap((p) => p.items.map((i) => i.id)) ?? []
    const readMap = loadReadMap()
    ids.forEach((id) => {
      readMap[id] = true
    })
    saveReadMap(readMap)
    setInfinitePagesRead(() => true)
    void queryClient.invalidateQueries({
      queryKey: [...NOTIFICATIONS_QUERY_KEY, conversationStarted],
    })
    toast.success("All loaded notifications are marked as read.")
  }, [queryClient, conversationStarted, setInfinitePagesRead, typeFilter])

  return {
    notifications: flatNotifications,
    hasNextPage: infinite.hasNextPage,
    fetchNextPage: infinite.fetchNextPage,
    isFetchingNextPage: infinite.isFetchingNextPage,
    isLoading: infinite.isPending,
    isError: infinite.isError,
    refetch: infinite.refetch,
    markAsRead,
    markAllAsRead,
  }
}
