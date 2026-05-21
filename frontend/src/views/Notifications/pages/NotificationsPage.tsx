import { useEffect, useMemo, useRef, useState } from "react"
import { Link } from "react-router-dom"
import { SidebarProvider, SidebarTrigger } from "@/components/sidebar"
import { AppSidebar } from "@/layout/app-sidebar"
import { useIsMobile } from "@/hooks/useMobile"
import { Button } from "@/components/button"
import { Card } from "@/components/card"
import { Bell, Check, Loader2, Settings2 } from "lucide-react"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/tabs"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/select"
import { useNotificationsInfinite } from "@/hooks/useNotifications"
import { useNotificationUserSettings } from "@/hooks/useNotificationUserSettings"
import { type NotificationTypeFilter } from "@/services/dashboard"
import { NotificationCard } from "../components/NotificationCard"

type ConversationTypeFilter = Exclude<NotificationTypeFilter, "all">

const CONVERSATION_TYPE_FILTER_OPTIONS: Array<{
  value: ConversationTypeFilter
  label: string
  settingKey: "conversationStarted" | "conversationHostility" | "conversationFinalizedHostility"
}> = [
  {
    value: "conversation_started",
    label: "Conversation Started",
    settingKey: "conversationStarted",
  },
  {
    value: "conversation_hostility",
    label: "High Hostility",
    settingKey: "conversationHostility",
  },
  {
    value: "conversation_finalized_hostility",
    label: "Finalized Hostility",
    settingKey: "conversationFinalizedHostility",
  },
]

const EmptyNotificationsState = ({
  title,
  description,
  primaryAction,
}: {
  title: string
  description: string
  primaryAction?: { label: string; to: string }
}) => (
  <div className="flex flex-col items-center justify-center gap-4 px-4 py-16 text-center">
    <div className="rounded-full bg-muted p-4">
      <Bell className="h-12 w-12 text-muted-foreground" />
    </div>
    <h3 className="text-lg font-medium text-foreground">{title}</h3>
    <p className="max-w-sm text-sm text-muted-foreground">{description}</p>
    {primaryAction ? (
      <Button asChild className="rounded-full">
        <Link
          to={primaryAction.to}
          className="inline-flex items-center gap-2"
        >
          <Settings2 className="h-4 w-4 shrink-0" />
          {primaryAction.label}
        </Link>
      </Button>
    ) : null}
  </div>
)

const NotificationsPage = () => {
  const isMobile = useIsMobile()
  const [activeTab, setActiveTab] = useState("all")
  const [typeFilter, setTypeFilter] = useState<NotificationTypeFilter>("all")
  const allSentinelRef = useRef<HTMLDivElement>(null)
  const unreadSentinelRef = useRef<HTMLDivElement>(null)
  const { settings } = useNotificationUserSettings()

  const allowedTypeFilterOptions = useMemo(() => {
    const opts: Array<{ value: NotificationTypeFilter; label: string }> = [
      { value: "all", label: "All" },
    ]
    for (const row of CONVERSATION_TYPE_FILTER_OPTIONS) {
      if (settings[row.settingKey]) {
        opts.push({ value: row.value, label: row.label })
      }
    }
    return opts
  }, [settings])

  useEffect(() => {
    if (typeFilter === "all") return
    const allowed = allowedTypeFilterOptions.some((o) => o.value === typeFilter)
    if (!allowed) setTypeFilter("all")
  }, [typeFilter, allowedTypeFilterOptions])

  const unreadOnly = activeTab === "unread"

  const {
    notifications,
    markAllAsRead,
    markAsRead,
    hasNextPage,
    fetchNextPage,
    isFetchingNextPage,
    isLoading,
  } = useNotificationsInfinite({ typeFilter, unreadOnly })

  useEffect(() => {
    const sentinel =
      activeTab === "all"
        ? allSentinelRef.current
        : activeTab === "unread"
          ? unreadSentinelRef.current
          : null
    if (!sentinel) return

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && hasNextPage && !isFetchingNextPage) {
          void fetchNextPage()
        }
      },
      { root: null, rootMargin: "100px", threshold: 0.1 }
    )

    observer.observe(sentinel)
    return () => observer.disconnect()
  }, [
    activeTab,
    hasNextPage,
    isFetchingNextPage,
    fetchNextPage,
    notifications.length,
    unreadOnly,
  ])

  return (
    <SidebarProvider>
      <div className="min-h-screen flex w-full overflow-x-hidden">
        <AppSidebar />
        <main className="flex-1 flex flex-col bg-zinc-100 min-w-0 relative peer-data-[state=expanded]:md:ml-[calc(var(--sidebar-width)-2px)] peer-data-[state=collapsed]:md:ml-0 transition-[margin] duration-200">
          <SidebarTrigger className="fixed top-6 z-10 h-8 w-8 bg-white/50 backdrop-blur-sm hover:bg-white/70 rounded-full shadow-md transition-[left] duration-200" />
          <div className="flex-1 p-4 sm:p-6 lg:p-8">
            <div className="max-w-7xl mx-auto w-full">
            <div className="flex items-center justify-between mb-8">
              <div>
                <h1 className="text-3xl font-bold">Notifications</h1>
                <p className="text-muted-foreground mt-1">
                  Stay updated with your latest activities and alerts
                </p>
              </div>
              <div className="flex items-center gap-4">
                <Select
                  value={typeFilter}
                  onValueChange={(value) =>
                    setTypeFilter(value as NotificationTypeFilter)
                  }
                >
                  <SelectTrigger className="w-44">
                    <SelectValue placeholder="All" />
                  </SelectTrigger>
                  <SelectContent>
                    {allowedTypeFilterOptions.map((opt) => (
                      <SelectItem key={opt.value} value={opt.value}>
                        {opt.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Button size="sm" variant="outline" onClick={markAllAsRead}>
                  <Check className="h-4 w-4 mr-2" />
                  Mark all as read
                </Button>
              </div>
            </div>

            <Tabs
              value={activeTab}
              onValueChange={setActiveTab}
              className="space-y-4"
            >
              <TabsList>
                <TabsTrigger value="all">All</TabsTrigger>
                <TabsTrigger value="unread">Unread</TabsTrigger>
              </TabsList>
              <TabsContent value="all">
                <Card className="overflow-hidden">
                  {isLoading && notifications.length === 0 ? (
                    <div className="flex flex-col items-center justify-center gap-3 py-16 text-muted-foreground">
                      <Loader2
                        className="h-8 w-8 animate-spin"
                        aria-label="Loading notifications"
                      />
                      <p className="text-sm">Loading notifications…</p>
                    </div>
                  ) : notifications.length === 0 && !hasNextPage ? (
                    <EmptyNotificationsState
                      title="No notifications yet"
                      description="When there is activity you follow—such as new conversations, high hostility alerts, or workflow issues—it will show up here. You can choose which types you receive in Settings."
                      primaryAction={{
                        label: "Notification preferences",
                        to: "/settings/notifications",
                      }}
                    />
                  ) : (
                    <div className="p-2">
                      {notifications.map((notification) => (
                        <NotificationCard
                          key={notification.id}
                          notification={notification}
                          onMarkRead={markAsRead}
                        />
                      ))}
                      <div
                        ref={allSentinelRef}
                        className="h-1 w-full shrink-0"
                        aria-hidden
                      />
                      {isFetchingNextPage ? (
                        <div className="flex items-center justify-center py-4 border-t">
                          <Loader2
                            className="h-5 w-5 animate-spin text-muted-foreground"
                            aria-label="Loading more"
                          />
                          <span className="ml-2 text-sm text-muted-foreground">
                            Loading more...
                          </span>
                        </div>
                      ) : null}
                    </div>
                  )}
                </Card>
              </TabsContent>
              <TabsContent value="unread">
                <Card className="overflow-hidden">
                  {isLoading && notifications.length === 0 ? (
                    <div className="flex flex-col items-center justify-center gap-3 py-16 text-muted-foreground">
                      <Loader2
                        className="h-8 w-8 animate-spin"
                        aria-label="Loading notifications"
                      />
                      <p className="text-sm">Loading notifications…</p>
                    </div>
                  ) : notifications.length === 0 && !hasNextPage ? (
                    <EmptyNotificationsState
                      title="No unread notifications"
                      description="You are up to date. New unread items will appear in this tab when they arrive."
                    />
                  ) : (
                    <div className="p-2">
                      {notifications.map((notification) => (
                        <NotificationCard
                          key={notification.id}
                          notification={notification}
                          onMarkRead={markAsRead}
                        />
                      ))}
                      <div
                        ref={unreadSentinelRef}
                        className="h-1 w-full shrink-0"
                        aria-hidden
                      />
                      {isFetchingNextPage ? (
                        <div className="flex justify-center py-4 border-t">
                          <Loader2
                            className="h-5 w-5 animate-spin text-muted-foreground"
                            aria-label="Loading more"
                          />
                          <span className="ml-2 text-sm text-muted-foreground">
                            Loading more...
                          </span>
                        </div>
                      ) : null}
                    </div>
                  )}
                </Card>
              </TabsContent>
            </Tabs>
            </div>
          </div>
        </main>
      </div>
    </SidebarProvider>
  )
}

export default NotificationsPage
