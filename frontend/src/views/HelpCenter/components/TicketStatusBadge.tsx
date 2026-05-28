import { Badge } from "@/components/badge";
import { cn } from "@/helpers/utils";

const STATUS_STYLES: Record<string, string> = {
  sync_pending: "bg-amber-100 text-amber-900",
  new: "bg-blue-100 text-blue-900",
  open: "bg-blue-100 text-blue-900",
  active: "bg-indigo-100 text-indigo-900",
  in_progress: "bg-indigo-100 text-indigo-900",
  resolved: "bg-green-100 text-green-900",
  closed: "bg-gray-200 text-gray-800",
  unknown: "bg-gray-100 text-gray-700",
};

export function TicketStatusBadge({ status }: { status: string }) {
  const label = status.replace(/_/g, " ");
  return (
    <Badge variant="outline" className={cn("capitalize border-0", STATUS_STYLES[status] ?? STATUS_STYLES.unknown)}>
      {label}
    </Badge>
  );
}
