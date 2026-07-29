import {
  CheckCircle2,
  CircleAlert,
  Info,
  TriangleAlert,
} from "lucide-react"
import { Link } from "react-router-dom"

import { Badge } from "@/components/badge"
import { formatTimeAgo } from "@/helpers/formatters"
import { formatNotificationDescription } from "@/helpers/notificationDisplay"
import { Notification } from "../../../interfaces/notification.interface"
import { cn } from "@/helpers/utils"

interface NotificationCardProps {
  notification: Notification
  groupName?: string
  onMarkRead?: (id: string) => void
}

export const NotificationCard = ({
  notification,
  groupName,
  onMarkRead,
}: NotificationCardProps) => {
  const typeStyles = {
    info: { icon: Info, iconClassName: "text-blue-600 dark:text-blue-400" },
    success: { icon: CheckCircle2, iconClassName: "text-green-600 dark:text-green-400" },
    warning: { icon: TriangleAlert, iconClassName: "text-amber-600 dark:text-amber-400" },
    error: { icon: CircleAlert, iconClassName: "text-red-600 dark:text-red-400" },
  }

  const TypeIcon = typeStyles[notification.type].icon
  const displayTitle = notification.title
  const levelBadgeClass =
    notification.type === "error"
      ? "bg-red-100 text-red-700 border-red-200 dark:bg-red-500/20 dark:text-red-400 dark:border-red-500/30"
      : notification.type === "warning"
        ? "bg-amber-100 text-amber-700 border-amber-200 dark:bg-amber-500/20 dark:text-amber-400 dark:border-amber-500/30"
        : notification.type === "success"
          ? "bg-green-100 text-green-700 border-green-200 dark:bg-green-500/20 dark:text-green-400 dark:border-green-500/30"
          : "bg-blue-100 text-blue-700 border-blue-200 dark:bg-blue-500/20 dark:text-blue-400 dark:border-blue-500/30"

  return (
    <Link
      to={notification.actionUrl || "/notifications"}
      onClick={() => {
        if (!notification.read) {
          onMarkRead?.(notification.id)
        }
      }}
      className={cn(
        "relative mb-1 block max-w-full min-w-0 border-b border-border px-4 py-3 transition-colors hover:bg-muted last:mb-0 last:border-b-0",
        !notification.read && "rounded-md bg-blue-100/70 pr-16 dark:bg-blue-500/20"
      )}
    >
      {!notification.read && (
        <>
          <span className="pointer-events-none absolute right-3 top-2 shrink-0 rounded-full bg-blue-100 px-2 py-0.5 text-[10px] font-semibold text-blue-700 dark:bg-blue-500/20 dark:text-blue-400">
            New
          </span>
        </>
      )}
      <div className="flex min-w-0 max-w-full items-start gap-2">
        <TypeIcon
          className={cn(
            "mt-0.5 h-4 w-4 shrink-0",
            typeStyles[notification.type].iconClassName
          )}
        />
        <div className="min-w-0 flex-1 overflow-hidden">
          <div className="flex items-center gap-2">
            <p className="break-words text-sm font-medium text-foreground [overflow-wrap:anywhere]">
              {displayTitle}
            </p>
            <Badge variant="outline" className={cn("capitalize text-[10px] px-2 py-0", levelBadgeClass)}>
              {notification.type}
            </Badge>
            {groupName ? (
              <Badge variant="outline" className="text-[10px] px-2 py-0">
                {groupName}
              </Badge>
            ) : null}
          </div>
          <p className="mt-0.5 break-words text-xs text-muted-foreground line-clamp-3 [overflow-wrap:anywhere]">
            {formatNotificationDescription(notification)}
          </p>
          <p className="mt-1 text-[11px] text-muted-foreground">
            {formatTimeAgo(notification.timestamp)}
          </p>
        </div>
      </div>
    </Link>
  )
}