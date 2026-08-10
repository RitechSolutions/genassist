import type { ReactNode } from "react";
import { AlertTriangle, RefreshCw } from "lucide-react";
import { Button } from "@/components/button";

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
}: ListErrorStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-16 gap-4 text-center">
      <div className="rounded-full bg-destructive/10 p-4">
        {icon ?? <AlertTriangle className="h-10 w-10 text-destructive" />}
      </div>
      <h3 className="font-medium text-lg">{title}</h3>
      {message && (
        <p className="text-sm text-muted-foreground max-w-sm px-4">{message}</p>
      )}
      {onRetry && (
        <Button
          variant="outline"
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
