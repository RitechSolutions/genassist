import {
  CheckCircle2,
  CircleAlert,
  Info,
  TriangleAlert,
} from "lucide-react"
import { Link } from "react-router-dom"

import { formatTimeAgo } from "@/helpers/formatters"
import { Notification } from "../../../interfaces/notification.interface"
import { cn } from "@/helpers/utils"

interface NotificationCardProps {
  notification: Notification
  onMarkRead?: (id: string) => void
}

export const NotificationCard = ({
  notification,
  onMarkRead,
}: NotificationCardProps) => {
  const typeStyles = {
    info: { icon: Info, iconClassName: "text-blue-600" },
    success: { icon: CheckCircle2, iconClassName: "text-green-600" },
    warning: { icon: TriangleAlert, iconClassName: "text-amber-600" },
    error: { icon: CircleAlert, iconClassName: "text-red-600" },
  }

  const TypeIcon = typeStyles[notification.type].icon
  const conversationShortId = notification.id.startsWith("conversation_")
    ? `#${notification.id.split(":").pop()?.slice(-4) ?? ""}`
    : null

  const formattedDescription = conversationShortId
    ? notification.description
        .replace(/\(ID:\s*[^)]+\)/gi, `(${conversationShortId})`)
        .replace(/Conversation\s+[a-f0-9-]+\.{3}/gi, `Conversation ${conversationShortId}`)
    : notification.description

  return (
    <Link
      to={notification.actionUrl || "/notifications"}
      onClick={() => {
        if (!notification.read) {
          onMarkRead?.(notification.id)
        }
      }}
      className={cn(
        "relative mb-1 block max-w-full min-w-0 border-b border-zinc-100 px-4 py-3 transition-colors hover:bg-zinc-50 last:mb-0",
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
          <p className="break-words text-sm font-medium text-zinc-900 [overflow-wrap:anywhere]">
            {notification.title}
            {conversationShortId ? ` ${conversationShortId}` : ""}
          </p>
          <p className="mt-0.5 break-words text-xs text-zinc-500 line-clamp-3 [overflow-wrap:anywhere]">
            {formattedDescription}
          </p>
          <p className="mt-1 text-[11px] text-zinc-400">
            {formatTimeAgo(notification.timestamp)}
          </p>
        </div>
      </div>
    </Link>
  )
}