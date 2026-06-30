import { useCallback, useMemo } from "react"
import {
  useQueryClient,
  useInfiniteQuery,
  type InfiniteData,
} from "@tanstack/react-query"
import { toast } from "react-hot-toast"

import { isPollEnabled } from "@/config/api"
import { Notification } from "@/interfaces/notification.interface"
import {
  fetchDashboardNotificationsPage,
  markNotificationsRead,
  type NotificationTypeFilter,
} from "@/services/dashboard"
import { useNotificationUserSettings } from "@/hooks/useNotificationUserSettings"
import {
  NOTIFICATIONS_INFINITE_QUERY_KEY,
  NOTIFICATIONS_PAGE_SIZE,
  notificationsInfiniteQueryKey,
} from "@/constants/notificationFeed"

export {
  NOTIFICATIONS_INFINITE_QUERY_KEY,
  NOTIFICATIONS_PAGE_SIZE,
  notificationsInfiniteQueryKey,
} from "@/constants/notificationFeed"

type NotificationFeedPage = {
  items: Notification[]
  hasMore: boolean
}

export const useNotificationsInfinite = ({
  typeFilter = "all",
  levelFilter = "all",
}: {
  typeFilter?: NotificationTypeFilter
  levelFilter?: "all" | "info" | "success" | "warning" | "error"
} = {}) => {
  const queryClient = useQueryClient()
  const { settings } = useNotificationUserSettings()
  const {
    conversationStarted,
    conversationHostility,
    conversationFinalizedHostility,
    workflowFailed,
  } = settings
  const infiniteKey = [
    ...notificationsInfiniteQueryKey(conversationStarted, typeFilter, levelFilter),
    conversationHostility,
    conversationFinalizedHostility,
    workflowFailed,
  ] as const

  const infinite = useInfiniteQuery({
    queryKey: infiniteKey,
    queryFn: async ({ pageParam }): Promise<NotificationFeedPage> => {
      const skip = pageParam as number
      const page = await fetchDashboardNotificationsPage(
        NOTIFICATIONS_PAGE_SIZE,
        skip,
        conversationStarted,
        conversationHostility,
        conversationFinalizedHostility,
        workflowFailed,
        typeFilter,
        levelFilter
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
    refetchInterval: isPollEnabled ? 15000 : false,
  })

  const flatNotifications = useMemo(
    () => infinite.data?.pages.flatMap((p) => p.items) ?? [],
    [infinite.data]
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
    [
      queryClient,
      conversationStarted,
      conversationHostility,
      conversationFinalizedHostility,
      workflowFailed,
      typeFilter,
      levelFilter,
      infiniteKey,
    ]
  )

  const markAsRead = useCallback(
    async (id: string) => {
      const ok = await markNotificationsRead([id], true)
      if (!ok) return
      setInfinitePagesRead((n) => n.id === id)
      void queryClient.invalidateQueries({
        queryKey: NOTIFICATIONS_INFINITE_QUERY_KEY,
      })
    },
    [queryClient, setInfinitePagesRead]
  )

  const markAllAsRead = useCallback(() => {
    const markAll = async () => {
      const key = infiniteKey
      const pages = queryClient.getQueryData<InfiniteData<NotificationFeedPage>>(
        key
      )
      const ids = pages?.pages.flatMap((p) => p.items.map((i) => i.id)) ?? []
      if (ids.length === 0) return
      const ok = await markNotificationsRead(ids, true)
      if (!ok) return
      setInfinitePagesRead(() => true)
      void queryClient.invalidateQueries({
        queryKey: NOTIFICATIONS_INFINITE_QUERY_KEY,
      })
      toast.success("All loaded notifications are marked as read.")
    }
    void markAll()
  }, [queryClient, setInfinitePagesRead, infiniteKey])

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

/** Bell / sidebar preview — shares the infinite feed query (first page, default filters). */
export const useNotifications = () => {
  const queryClient = useQueryClient()
  const {
    notifications: feedNotifications,
    markAsRead,
    refetch,
  } = useNotificationsInfinite({ typeFilter: "all", levelFilter: "all" })

  const notifications = useMemo(
    () => feedNotifications.slice(0, NOTIFICATIONS_PAGE_SIZE),
    [feedNotifications]
  )

  const unreadCount = useMemo(
    () => notifications.filter((notification) => !notification.read).length,
    [notifications]
  )

  const markAllBellAsRead = useCallback(async () => {
    const unreadIds = notifications
      .filter((notification) => !notification.read)
      .map((notification) => notification.id)
    if (unreadIds.length === 0) return
    const ok = await markNotificationsRead(unreadIds, true)
    if (!ok) return
    void queryClient.invalidateQueries({
      queryKey: NOTIFICATIONS_INFINITE_QUERY_KEY,
    })
    toast.success("All notifications are marked as read.")
  }, [notifications, queryClient])

  return {
    notifications,
    unreadCount,
    markAllAsRead: markAllBellAsRead,
    markAsRead,
    refetch,
  }
}
