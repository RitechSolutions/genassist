import { Badge } from "@/components/badge";
import { cn } from "@/helpers/utils";

/**
 * Maps a status to a color bucket. Statuses are the live Azure DevOps work item
 * states (which vary by work item type and process, e.g. "To Do", "In Progress",
 * "In Review", "Done"), plus the local "sync_pending" placeholder. Matching is
 * case-insensitive and space/underscore-insensitive so custom states still color
 * sensibly; anything unrecognized falls back to neutral.
 */
const STATUS_BUCKETS: Array<[string[], string]> = [
  [["sync pending", "syncing"], "bg-amber-100 text-amber-900"],
  [["new", "to do", "proposed", "approved", "open"], "bg-blue-100 text-blue-900"],
  [["active", "in progress", "committed", "doing"], "bg-indigo-100 text-indigo-900"],
  [["on hold", "blocked"], "bg-orange-100 text-orange-900"],
  [["test", "testing", "in review", "review", "resolved"], "bg-purple-100 text-purple-900"],
  [["done", "closed", "completed"], "bg-green-100 text-green-900"],
  [["removed", "cancelled", "canceled", "rejected", "abandoned"], "bg-gray-200 text-gray-700"],
];

const FALLBACK_STYLE = "bg-gray-100 text-gray-700";

function statusStyle(status: string): string {
  const normalized = status.toLowerCase().replace(/[\s_]+/g, " ").trim();
  for (const [keys, style] of STATUS_BUCKETS) {
    if (keys.includes(normalized)) return style;
  }
  return FALLBACK_STYLE;
}

export function TicketStatusBadge({ status }: { status: string }) {
  const label = status === "sync_pending" ? "Syncing" : status.replace(/_/g, " ");
  return (
    <Badge variant="outline" className={cn("capitalize border-0", statusStyle(status))}>
      {label}
    </Badge>
  );
}
