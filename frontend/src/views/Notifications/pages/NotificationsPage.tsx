import { useEffect, useMemo, useRef, useState } from "react"
import { SidebarProvider, SidebarTrigger } from "@/components/sidebar"
import { AppSidebar } from "@/layout/app-sidebar"
import { useIsMobile } from "@/hooks/useMobile"
import { Button } from "@/components/button"
import { BellOff, Check, Loader2 } from "lucide-react"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/tabs"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/select"
import { useNotificationsInfinite } from "@/hooks/useNotifications"
import { type NotificationTypeFilter } from "@/services/dashboard"
import { NotificationCard } from "../components/NotificationCard"

const EmptyNotificationsState = ({ message }: { message: string }) => (
  <div className="flex flex-col items-center justify-center py-12 gap-4 text-center">
    <BellOff className="h-12 w-12 text-gray-400" />
    <h3 className="font-medium text-lg">No notifications found</h3>
    <p className="text-sm text-gray-500 max-w-sm">{message}</p>
  </div>
)

const NotificationsPage = () => {
  const isMobile = useIsMobile()
  const [activeTab, setActiveTab] = useState("all")
  const [typeFilter, setTypeFilter] = useState<NotificationTypeFilter>("all")
  const allSentinelRef = useRef<HTMLDivElement>(null)
  const unreadSentinelRef = useRef<HTMLDivElement>(null)

  const {
    notifications,
    markAllAsRead,
    markAsRead,
    hasNextPage,
    fetchNextPage,
    isFetchingNextPage,
    isLoading,
  } = useNotificationsInfinite({ typeFilter })

  const filteredNotifications = notifications

  const unreadNotifications = useMemo(
    () => filteredNotifications.filter((n) => !n.read),
    [filteredNotifications]
  )

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
      { root: null, rootMargin: "200px", threshold: 0 }
    )

    observer.observe(sentinel)
    return () => observer.disconnect()
  }, [
    activeTab,
    hasNextPage,
    isFetchingNextPage,
    fetchNextPage,
    filteredNotifications.length,
    unreadNotifications.length,
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
                    <SelectItem value="all">All</SelectItem>
                    <SelectItem value="conversation_started">
                      Conversation Started
                    </SelectItem>
                    <SelectItem value="conversation_hostility">
                      High Hostility
                    </SelectItem>
                    <SelectItem value="conversation_finalized_hostility">
                      Finalized Hostility
                    </SelectItem>
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
                <div className="overflow-hidden rounded-lg border bg-white p-2 shadow-sm">
                  {isLoading && filteredNotifications.length === 0 ? (
                    <p className="text-center text-gray-500 p-6">
                      Loading notifications…
                    </p>
                  ) : filteredNotifications.length === 0 && !hasNextPage ? (
                    <EmptyNotificationsState message="You're all caught up. New updates will appear here." />
                  ) : (
                    <>
                      {filteredNotifications.map((notification) => (
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
                        <div className="flex justify-center py-3">
                          <Loader2
                            className="h-5 w-5 animate-spin text-muted-foreground"
                            aria-label="Loading more"
                          />
                        </div>
                      ) : null}
                    </>
                  )}
                </div>
              </TabsContent>
              <TabsContent value="unread">
                <div className="overflow-hidden rounded-lg border bg-white p-2 shadow-sm">
                  {isLoading && filteredNotifications.length === 0 ? (
                    <p className="text-center text-gray-500 p-6">
                      Loading notifications…
                    </p>
                  ) : unreadNotifications.length === 0 && !hasNextPage ? (
                    <EmptyNotificationsState message="No unread notifications right now." />
                  ) : (
                    <>
                      {unreadNotifications.map((notification) => (
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
                        <div className="flex justify-center py-3">
                          <Loader2
                            className="h-5 w-5 animate-spin text-muted-foreground"
                            aria-label="Loading more"
                          />
                        </div>
                      ) : null}
                    </>
                  )}
                </div>
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
