import { useMemo } from "react";
import { Card } from "@/components/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/table";
import { Loader2, View, ScrollText } from "lucide-react";
import { Button } from "@/components/button";
import { formatDate, getTimeFromDatetime } from "@/helpers/utils";
import { AuditLogCardProps } from "@/interfaces/audit-log.interface";
import { TableSkeleton } from "@/components/skeletons";
import { ListEmptyState } from "@/components/ListEmptyState";
import { ListErrorState } from "@/components/ListErrorState";
import Can from "@/hooks/Can";

const AUDIT_LOG_TABLE_COLUMNS = 6;

export function AuditLogCard({
  searchQuery,
  auditLogs,
  users,
  selectedUser,
  onViewDetails,
  loading = false,
  isRefreshing = false,
  error = null,
  onRetry,
}: AuditLogCardProps) {
  const filteredAuditLogs = useMemo(() => {
    return auditLogs.filter((log) => {
      const matchesSearch =
        log.table_name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
        log.action_name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
        log.modified_by?.toLowerCase().includes(searchQuery.toLowerCase());

      const matchesUser = selectedUser
        ? log.modified_by === selectedUser
        : true;

      return matchesSearch && matchesUser;
    });
  }, [auditLogs, searchQuery, selectedUser]);

  const getUsername = (id: string) =>
    users.find((user) => user.id === id)?.username || "Unknown User";

  if (loading) {
    return <TableSkeleton columns={AUDIT_LOG_TABLE_COLUMNS} rows={8} />;
  }

  if (error) {
    return (
      <Card className="overflow-hidden shadow-sm dark:bg-zinc-900">
        <ListErrorState message={error} onRetry={onRetry} />
      </Card>
    );
  }

  if (filteredAuditLogs.length === 0) {
    return (
      <Card className="overflow-hidden shadow-sm dark:bg-zinc-900">
        <ListEmptyState
          icon={<ScrollText className="h-12 w-12 text-muted-foreground" />}
          title={searchQuery ? "No matching audit logs" : "No audit logs yet"}
          description={
            searchQuery
              ? "No audit logs match your search or filters. Try widening the date range or clearing a filter."
              : "System changes are recorded here. Adjust the date range or filters if you expected to see entries."
          }
        />
      </Card>
    );
  }

  return (
    <Card className="p-8 overflow-hidden">
      <div className="relative">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Log Id</TableHead>
              <TableHead>Date</TableHead>
              <TableHead>Table Name</TableHead>
              <TableHead>Action</TableHead>
              <TableHead>User</TableHead>
              <Can permissions={["read:audit_log"]}>
                <TableHead>Details</TableHead>
              </Can>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filteredAuditLogs.map((log) => (
              <TableRow key={log.id}>
                <TableCell>{log.id}</TableCell>
                <TableCell>
                  {formatDate(log.modified_at)} -{" "}
                  {getTimeFromDatetime(log.modified_at)}
                </TableCell>
                <TableCell>{log.table_name}</TableCell>
                <TableCell>{log.action_name}</TableCell>
                <TableCell>{getUsername(log.modified_by)}</TableCell>
                <Can permissions={["read:audit_log"]}>
                  <TableCell>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => onViewDetails(log.id)}
                      title="View Details"
                    >
                      <View size="24" />
                    </Button>
                  </TableCell>
                </Can>
              </TableRow>
            ))}
          </TableBody>
        </Table>

        {isRefreshing && (
          <div className="absolute inset-0 flex items-center justify-center bg-background/60 backdrop-blur-[1px] rounded-md">
            <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
          </div>
        )}
      </div>
    </Card>
  );
}
