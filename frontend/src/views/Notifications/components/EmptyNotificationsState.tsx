import { Link } from "react-router-dom"
import { Bell, Settings2 } from "lucide-react"

import { Button } from "@/components/button"
import { cn } from "@/helpers/utils"

export type EmptyNotificationsStateProps = {
  title: string
  description: string
  primaryAction?: { label: string; to: string }
  compact?: boolean
}

export function EmptyNotificationsState({
  title,
  description,
  primaryAction,
  compact = false,
}: EmptyNotificationsStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-4 px-4 text-center",
        compact ? "py-8" : "py-16"
      )}
    >
      <div className={cn("rounded-full bg-muted p-4", compact && "p-3")}>
        <Bell
          className={cn(
            "text-muted-foreground",
            compact ? "h-8 w-8" : "h-12 w-12"
          )}
        />
      </div>
      <h3
        className={cn(
          "font-medium text-foreground",
          compact ? "text-base" : "text-lg"
        )}
      >
        {title}
      </h3>
      <p
        className={cn(
          "max-w-sm text-muted-foreground",
          compact ? "px-2 text-xs" : "text-sm"
        )}
      >
        {description}
      </p>
      {primaryAction ? (
        <Button
          asChild
          className="rounded-full"
          size={compact ? "sm" : "default"}
        >
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
}
