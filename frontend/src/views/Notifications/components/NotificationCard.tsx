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
    info: { icon: Info, iconClassName: "text-blue-600" },
    success: { icon: CheckCircle2, iconClassName: "text-green-600" },
    warning: { icon: TriangleAlert, iconClassName: "text-amber-600" },
    error: { icon: CircleAlert, iconClassName: "text-red-600" },
  }

  const TypeIcon = typeStyles[notification.type].icon
  const displayTitle = notification.title
  const levelBadgeClass =
    notification.type === "error"
      ? "bg-red-100 text-red-700 border-red-200"
      : notification.type === "warning"
        ? "bg-amber-100 text-amber-700 border-amber-200"
        : notification.type === "success"
          ? "bg-green-100 text-green-700 border-green-200"
          : "bg-blue-100 text-blue-700 border-blue-200"

  return (
    <Link
      to={notification.actionUrl || "/notifications"}
      onClick={() => {
        if (!notification.read) {
          onMarkRead?.(notification.id)
        }
      }}
      className={cn(
        "relative mb-1 block max-w-full min-w-0 border-b border-zinc-100 px-4 py-3 transition-colors hover:bg-zinc-50 last:mb-0 last:border-b-0",
        !notification.read && "rounded-md bg-blue-100/70 pr-16"
      )}
    >
      {!notification.read && (
        <>
          <span className="pointer-events-none absolute right-3 top-2 shrink-0 rounded-full bg-blue-100 px-2 py-0.5 text-[10px] font-semibold text-blue-700">
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
            <p className="break-words text-sm font-medium text-zinc-900 [overflow-wrap:anywhere]">
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
          <p className="mt-0.5 break-words text-xs text-zinc-500 line-clamp-3 [overflow-wrap:anywhere]">
            {formatNotificationDescription(notification)}
          </p>
          <p className="mt-1 text-[11px] text-zinc-400">
            {formatTimeAgo(notification.timestamp)}
          </p>
        </div>
      </div>
    </Link>
  )
}