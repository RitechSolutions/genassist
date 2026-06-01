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
  markNotificationsRead,
  type NotificationTypeFilter,
} from "@/services/dashboard"
import { useWebSocketDashboardContext } from "@/context/WebSocketDashboardContext"
import { useNotificationUserSettings } from "@/hooks/useNotificationUserSettings"

export const NOTIFICATIONS_QUERY_KEY = ["notifications-feed"] as const
export const NOTIFICATIONS_INFINITE_QUERY_KEY = [
  "notifications-feed-infinite",
] as const

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

const NOTIFICATIONS_BELL_LIMIT = 10
const NOTIFICATIONS_PAGE_SIZE = 20

type NotificationFeedPage = {
  items: Notification[]
  hasMore: boolean
}

export const useNotifications = () => {
  const queryClient = useQueryClient()
  const { subscribe } = useWebSocketDashboardContext()
  const { settings } = useNotificationUserSettings()
  const {
    conversationStarted,
    conversationHostility,
    conversationFinalizedHostility,
    workflowFailed,
  } = settings

  const { data: notifications = [], refetch } = useQuery<Notification[]>({
    queryKey: [
      ...NOTIFICATIONS_QUERY_KEY,
      conversationStarted,
      conversationHostility,
      conversationFinalizedHostility,
      workflowFailed,
    ],
    queryFn: async () => {
      const items = await fetchDashboardNotifications(NOTIFICATIONS_BELL_LIMIT, {
        includeConversationStarted: conversationStarted,
        includeConversationHostility: conversationHostility,
        includeConversationFinalizedHostility: conversationFinalizedHostility,
        includeWorkflowFailed: workflowFailed,
      })
      return items ?? []
    },
    refetchInterval: isPollEnabled ? 15000 : false,
  })

  const updateCachedNotifications = useCallback(
    (updater: (prev: Notification[]) => Notification[]) => {
      queryClient.setQueryData<Notification[]>(
        [
          ...NOTIFICATIONS_QUERY_KEY,
          conversationStarted,
          conversationHostility,
          conversationFinalizedHostility,
          workflowFailed,
        ],
        (prev) => updater(prev ?? [])
      )
    },
    [
      queryClient,
      conversationStarted,
      conversationHostility,
      conversationFinalizedHostility,
      workflowFailed,
    ]
  )

  const markAllAsRead = async () => {
    const unreadIds = notifications
      .filter((notification) => !notification.read)
      .map((notification) => notification.id)
    if (unreadIds.length === 0) return
    const ok = await markNotificationsRead(unreadIds, true)
    if (!ok) return
    updateCachedNotifications((prev) =>
      prev.map((notification) => ({ ...notification, read: true }))
    )
    toast.success("All notifications are marked as read.")
  }

  const markAsRead = async (id: string) => {
    const ok = await markNotificationsRead([id], true)
    if (!ok) return
    updateCachedNotifications((prev) =>
      prev.map((notification) =>
        notification.id === id ? { ...notification, read: true } : notification
      )
    )
  }

  const handleSocketMessage = useCallback(
    (data: Record<string, unknown>) => {
      const topic = String(data.type ?? data.topic ?? data.msg_type ?? "")
      if (topic !== "notification") return
      // In WS mode, always refetch persisted notifications from DB to avoid
      // payload-shape drift and to keep user_notification IDs/states accurate.
      void refetch()
      void queryClient.invalidateQueries({ queryKey: NOTIFICATIONS_INFINITE_QUERY_KEY })
    },
    [
      queryClient,
      refetch,
    ]
  )

  useEffect(() => subscribe(handleSocketMessage), [subscribe, handleSocketMessage])

  useEffect(() => {
    void refetch()
  }, [
    conversationStarted,
    conversationHostility,
    conversationFinalizedHostility,
    workflowFailed,
    refetch,
  ])

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
        queryKey: [
          ...NOTIFICATIONS_QUERY_KEY,
          conversationStarted,
          conversationHostility,
          conversationFinalizedHostility,
          workflowFailed,
        ],
      })
    },
    [
      queryClient,
      conversationStarted,
      conversationHostility,
      conversationFinalizedHostility,
      workflowFailed,
      setInfinitePagesRead,
    ]
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
        queryKey: [
          ...NOTIFICATIONS_QUERY_KEY,
          conversationStarted,
          conversationHostility,
          conversationFinalizedHostility,
          workflowFailed,
        ],
      })
      toast.success("All loaded notifications are marked as read.")
    }
    void markAll()
  }, [
    queryClient,
    conversationStarted,
    conversationHostility,
    conversationFinalizedHostility,
    workflowFailed,
    setInfinitePagesRead,
    infiniteKey,
  ])

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
