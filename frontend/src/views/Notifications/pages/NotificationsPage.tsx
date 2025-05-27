import { SidebarProvider } from "@/components/sidebar"
import { AppSidebar } from "@/layout/app-sidebar"
import { useIsMobile } from "@/hooks/useMobile"
import { Button } from "@/components/button"
import { Bell, Check, Filter } from "lucide-react"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/tabs"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/dropdown-menu"
import { useNotifications } from "../hooks/useNotifications"
import { NotificationCard } from "../components/NotificationCard"

const NotificationsPage = () => {
  const isMobile = useIsMobile()
  const { notifications, markAllAsRead } = useNotifications()

  return (
    <SidebarProvider>
      <div className="min-h-screen flex w-full">
        {!isMobile && <AppSidebar />}
        <main className="flex-1 p-8">
          <div className="max-w-4xl mx-auto">
            <div className="flex items-center justify-between mb-8">
              <div>
                <h1 className="text-3xl font-bold flex items-center gap-2">
                  <Bell className="w-8 h-8" /> Notifications
                </h1>
                <p className="text-muted-foreground mt-1">
                  Stay updated with your latest activities and alerts
                </p>
              </div>
              <div className="flex items-center gap-4">
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button variant="outline" size="sm">
                      <Filter className="h-4 w-4 mr-2" />
                      Filter
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent>
                    <DropdownMenuLabel>Filter by Type</DropdownMenuLabel>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem>All</DropdownMenuItem>
                    <DropdownMenuItem>Unread</DropdownMenuItem>
                    <DropdownMenuItem>System</DropdownMenuItem>
                    <DropdownMenuItem>Reports</DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
                <Button size="sm" variant="outline" onClick={markAllAsRead}>
                  <Check className="h-4 w-4 mr-2" />
                  Mark all as read
                </Button>
              </div>
            </div>

            <Tabs defaultValue="all" className="space-y-4">
              <TabsList>
                <TabsTrigger value="all">All</TabsTrigger>
                <TabsTrigger value="unread">Unread</TabsTrigger>
                <TabsTrigger value="archived">Archived</TabsTrigger>
              </TabsList>
              <TabsContent value="all" className="space-y-4">
                {notifications.map((notification) => (
                  <NotificationCard key={notification.id} notification={notification} />
                ))}
              </TabsContent>
              <TabsContent value="unread" className="space-y-4">
                {notifications
                  .filter((n) => !n.read)
                  .map((notification) => (
                    <NotificationCard key={notification.id} notification={notification} />
                  ))}
              </TabsContent>
              <TabsContent value="archived" className="space-y-4">
                <p className="text-center text-muted-foreground py-8">
                  No archived notifications
                </p>
              </TabsContent>
            </Tabs>
          </div>
        </main>
      </div>
    </SidebarProvider>
  )
}

export default NotificationsPage 