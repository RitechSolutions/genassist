import { Bell, CheckCircle2, CircleAlert, Info, TriangleAlert } from "lucide-react"
import { Link } from "react-router-dom"

import { Button } from "@/components/button"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/popover"
import { ScrollArea } from "@/components/scroll-area"
import { formatTimeAgo } from "@/helpers/formatters"
import { formatNotificationDescription } from "@/helpers/notificationDisplay"
import { useNotifications } from "@/hooks/useNotifications"
import { Notification } from "@/interfaces/notification.interface"
import { cn } from "@/helpers/utils"

type NotificationBellPopoverProps = {
  maxItems?: number
  className?: string
  /** Smaller trigger (e.g. sidebar beside avatar) */
  compact?: boolean
}

const notificationTypeStyle: Record<
  Notification["type"],
  { icon: typeof Info; iconClassName: string }
> = {
  info: {
    icon: Info,
    iconClassName: "text-blue-600",
  },
  success: {
    icon: CheckCircle2,
    iconClassName: "text-green-600",
  },
  warning: {
    icon: TriangleAlert,
    iconClassName: "text-amber-600",
  },
  error: {
    icon: CircleAlert,
    iconClassName: "text-red-600",
  },
}

function formatNotificationTimestamp(timestamp: string): string {
  try {
    return formatTimeAgo(timestamp)
  } catch {
    return timestamp
  }
}

export function NotificationBellPopover({
  maxItems = 10,
  className,
  compact = false,
}: NotificationBellPopoverProps) {
  const { notifications, markAsRead } = useNotifications()

  const unreadCount = notifications.filter((notification) => !notification.read).length
  const previewItems = notifications.slice(0, maxItems)

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          size="icon"
          aria-label="Open notifications"
          className={cn(
            "relative border-zinc-200 bg-white hover:bg-zinc-50",
            compact &&
              "h-7 w-7 min-h-7 min-w-7 shrink-0 rounded-md border focus-visible:ring-1 focus-visible:ring-zinc-200 [&_svg]:!size-3.5",
            className
          )}
        >
          <Bell className={cn(compact ? "size-3.5" : "h-4 w-4")} />
          {unreadCount > 0 && (
            <span
              className={cn(
                "absolute inline-flex items-center justify-center rounded-full bg-red-500 font-semibold text-white",
                compact
                  ? "-right-0.5 -top-0.5 min-h-3.5 min-w-3.5 px-0.5 text-[8px] leading-none"
                  : "-right-1 -top-1 min-w-5 px-1 text-[10px] leading-4"
              )}
            >
              {unreadCount > 9 ? "9+" : unreadCount}
            </span>
          )}
        </Button>
      </PopoverTrigger>

      <PopoverContent
        align="end"
        className="w-[min(100vw-1.5rem,340px)] max-w-[340px] p-0 overflow-x-hidden"
      >
        <div className="px-4 py-3">
          <p className="text-sm font-semibold text-zinc-900">Notifications</p>
        </div>

        <ScrollArea className="h-[320px] max-w-full">
          <div className="min-w-0 max-w-full px-2 pt-1 pb-1">
            {previewItems.length === 0 ? (
              <p className="px-2 py-4 text-center text-sm text-zinc-500">
                No notifications yet.
              </p>
            ) : (
              previewItems.map((notification) => {
                const typeMeta = notificationTypeStyle[notification.type]
                const TypeIcon = typeMeta.icon
                const formattedDescription = formatNotificationDescription(notification)

                return (
                  <Link
                    key={notification.id}
                    to={notification.actionUrl || "/notifications"}
                    onClick={() => {
                      if (!notification.read) {
                        markAsRead(notification.id)
                      }
                    }}
                    className={cn(
                      "relative mb-1 block max-w-full min-w-0 border-b border-zinc-100 px-2 py-3 transition-colors hover:bg-zinc-50 last:mb-0",
                      !notification.read && "rounded-md bg-blue-100/70 pr-14"
                    )}
                  >
                    {!notification.read && (
                      <>
                        <span className="pointer-events-none absolute right-2 top-2 shrink-0 rounded-full bg-blue-100 px-2 py-0.5 text-[10px] font-semibold text-blue-700">
                          New
                        </span>
                      </>
                    )}
                    <div className="flex min-w-0 max-w-full items-start gap-2">
                      <TypeIcon
                        className={cn("mt-0.5 h-4 w-4 shrink-0", typeMeta.iconClassName)}
                      />
                    <div className="min-w-0 flex-1 overflow-hidden">
                      <p className="break-words text-sm font-medium text-zinc-900 [overflow-wrap:anywhere]">
                        {notification.title}
                      </p>
                      <p className="mt-0.5 break-words text-xs text-zinc-500 line-clamp-3 [overflow-wrap:anywhere]">
                        {formattedDescription}
                      </p>
                      <p className="mt-1 text-[11px] text-zinc-400">
                        {formatNotificationTimestamp(notification.timestamp)}
                      </p>
                    </div>
                  </div>
                  </Link>
                )
              })
            )}
          </div>
        </ScrollArea>

        <div className="border-t px-3 py-2">
          <Link
            to="/notifications"
            className="block rounded-md px-2 py-1.5 text-center text-sm font-medium text-blue-600 hover:bg-blue-50"
          >
            View all
          </Link>
        </div>
      </PopoverContent>
    </Popover>
  )
}
