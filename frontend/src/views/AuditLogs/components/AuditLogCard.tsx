import { Loader2, ScrollText } from "lucide-react";
import { Column } from "@/components/ui/data-table";
import { EntityTableCard } from "@/components/EntityTableCard";
import { formatDate, getTimeFromDatetime } from "@/helpers/utils";
import { AuditLog, AuditLogCardProps } from "@/interfaces/audit-log.interface";
import { usePermissions } from "@/context/PermissionContext";

const matchesSearch = (log: AuditLog, query: string) => {
  const q = query.trim().toLowerCase();
  return (
    !!log.table_name?.toLowerCase().includes(q) ||
    !!log.action_name?.toLowerCase().includes(q) ||
    !!log.modified_by?.toLowerCase().includes(q)
  );
};

export function AuditLogCard({
  searchQuery,
  auditLogs,
  users,
  onViewDetails,
  loading = false,
  isRefreshing = false,
  error = null,
  onRetry,
}: AuditLogCardProps) {
  const canViewDetails = usePermissions().includes("read:audit_log");

  const getUsername = (id: string) =>
    users.find((user) => user.id === id)?.username || "Unknown User";

  const columns: Column<AuditLog>[] = [
    {
      header: "Log Id",
      key: "id",
      cell: (log) => log.id,
      className: "break-all",
    },
    {
      header: "Date",
      key: "modified_at",
      cell: (log) => `${formatDate(log.modified_at)} at ${getTimeFromDatetime(log.modified_at)}`,
      className: "whitespace-nowrap",
    },
    {
      header: "Table Name",
      key: "table_name",
      cell: (log) => log.table_name,
    },
    {
      header: "Action",
      key: "action_name",
      cell: (log) => log.action_name,
    },
    {
      header: "User",
      key: "modified_by",
      cell: (log) => getUsername(log.modified_by),
    },
  ];

  return (
    <div className="relative">
      <EntityTableCard<AuditLog>
        data={auditLogs}
        loading={loading}
        error={error}
        onRetry={onRetry}
        errorTitle="Couldn't load audit logs"
        searchQuery={searchQuery}
        filterFn={matchesSearch}
        columns={columns}
        // The page paginates server-side, so the table's own client-side paging is off.
        pageSize={0}
        onRowClick={canViewDetails ? (log) => onViewDetails(log.id) : undefined}
        emptyState={{
          icon: <ScrollText className="h-12 w-12 text-muted-foreground" />,
          title: "No audit logs yet",
          description:
            "System changes are recorded here. Adjust the date range or filters if you expected to see entries.",
          searchTitle: "No matching audit logs",
          searchDescription:
            "No audit logs match your search or filters. Try widening the date range or clearing a filter.",
        }}
      />

      {isRefreshing && (
        <div className="absolute inset-0 flex items-center justify-center rounded-md bg-background/60 backdrop-blur-[1px]">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      )}
    </div>
  );
}
