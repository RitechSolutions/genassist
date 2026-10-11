import type { ReactNode } from "react";
import { AlertTriangle, RefreshCw } from "lucide-react";
import { Button } from "@/components/button";
import { cn } from "@/helpers/utils";

export type ListErrorStateProps = {
  /** The error message to show (e.g. "Failed to fetch deployments"). */
  message?: ReactNode;
  /** Heading above the message. Defaults to "Couldn't load data". */
  title?: string;
  /** Custom icon. Defaults to a destructive AlertTriangle. */
  icon?: ReactNode;
  /** When provided, renders a retry button that calls this handler. */
  onRetry?: () => void;
  /** Retry button label. Defaults to "Try again". */
  retryLabel?: string;
  /** Tighter spacing and smaller icon/heading, for use inside a dialog or form section. */
  compact?: boolean;
};

/**
 * Shared error state for list/table views. Visually parallels `ListEmptyState`
 * (centered icon-in-circle + heading + description) but uses a destructive accent
 * and an optional "Try again" action. Rendered inside the table's `<Card>`.
 */
export function ListErrorState({
  message,
  title = "Couldn't load data",
  icon,
  onRetry,
  retryLabel = "Try again",
  compact = false,
}: ListErrorStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center text-center",
        compact ? "py-6 gap-3" : "py-16 gap-4"
      )}
    >
      <div className={cn("rounded-full bg-destructive/10", compact ? "p-3" : "p-4")}>
        {icon ?? (
          <AlertTriangle
            className={cn("text-destructive", compact ? "h-6 w-6" : "h-10 w-10")}
          />
        )}
      </div>
      <h3 className={cn("font-medium", compact ? "text-sm" : "text-lg")}>{title}</h3>
      {message && (
        <p className="text-sm text-muted-foreground max-w-sm px-4">{message}</p>
      )}
      {onRetry && (
        <Button
          type="button"
          variant="outline"
          size={compact ? "sm" : undefined}
          onClick={onRetry}
          className="rounded-full gap-2"
        >
          <RefreshCw className="h-4 w-4" />
          {retryLabel}
        </Button>
      )}
    </div>
  );
}
