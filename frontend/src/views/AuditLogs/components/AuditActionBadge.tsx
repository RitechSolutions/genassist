import { Badge } from "@/components/badge";
import { cn } from "@/helpers/utils";

const ACTION_BADGE_CLASS: Record<string, string> = {
  Insert: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-400",
  Update: "bg-amber-500/15 text-amber-700 dark:text-amber-400",
  Delete: "bg-red-500/15 text-red-700 dark:text-red-400",
};

/** Colour-coded audit action: green Insert, amber Update, red Delete, neutral for anything else. */
export function AuditActionBadge({ action }: { action: string }) {
  return (
    <Badge
      variant="outline"
      className={cn("border-transparent", ACTION_BADGE_CLASS[action] ?? "bg-muted text-foreground")}
    >
      {action}
    </Badge>
  );
}
