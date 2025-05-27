import { useState, useMemo, useEffect } from "react";
import { Card } from "@/components/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/table";
import { Loader2, View, Search, XCircle } from "lucide-react";
import { Button } from "@/components/button";
import { formatDate, getTimeFromDatetime } from "@/helpers/utils";
import { AuditLogCardProps } from "@/interfaces/audit-log.interface";
import Can from "@/hooks/Can";

export function AuditLogCard({
  searchQuery,
  auditLogs,
  users,
  selectedUser,
  onViewDetails,
}: AuditLogCardProps) {
  const [loading, setLoading] = useState<boolean>(false);
  const [error] = useState<string | null>(null);

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

  useEffect(() => {
    setLoading(true);
    const timeout = setTimeout(() => {
      setLoading(false);
    }, 2000);
    return () => clearTimeout(timeout);
  }, []);

  if (error) {
    return (
      <Card className="p-8">
        <div className="text-center text-red-500">{error}</div>
      </Card>
    );
  }

  return (
    <Card className="p-8">
      <div className="flex items-center gap-2 text-muted-foreground">
        {loading ? (
          <>
            <Loader2 className="w-5 h-5 animate-spin" />
            Loading audit logs, please wait...
          </>
        ) : filteredAuditLogs.length === 0 ? (
          <>
            <XCircle className="w-5 h-5" />
            <span>
              {searchQuery
                ? "No results found for this search query."
                : "No audit logs available."}
            </span>
          </>
        ) : null}
      </div>

      {!loading && filteredAuditLogs.length > 0 && (
        <Table>
          <TableHeader>
            <TableRow>
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
      )}
    </Card>
  );
}
