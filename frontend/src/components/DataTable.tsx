import { ReactNode } from "react";
import { cn } from "@/helpers/utils";
import { Card } from "@/components/card";
import { Loader2 } from "lucide-react";
import {
  Table,
  TableBody,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/table";

interface DataTableProps<T> {
  data: T[];
  loading: boolean;
  error?: string | null;
  searchQuery: string;
  headers: (string | { label: string; className?: string })[];
  renderRow: (item: T, index: number) => ReactNode;
  emptyMessage?: string;
  searchEmptyMessage?: string;
}

export function DataTable<T>({
  data,
  loading,
  error,
  searchQuery,
  headers,
  renderRow,
  emptyMessage = "No data found",
  searchEmptyMessage = "No data found matching your search",
}: DataTableProps<T>) {
  if (loading) {
    return (
      <Card className="p-8 flex justify-center items-center">
        <Loader2 className="w-6 h-6 animate-spin" />
      </Card>
    );
  }

  if (error) {
    return (
      <Card className="p-8">
        <div className="text-center text-red-500">{error}</div>
      </Card>
    );
  }

  if (data.length === 0) {
    return (
      <Card className="p-8">
        <div className="text-center text-muted-foreground">
          {searchQuery ? searchEmptyMessage : emptyMessage}
        </div>
      </Card>
    );
  }

  return (
    <Card>
      <Table className="table-fixed">
        <TableHeader>
          <TableRow>
            {headers.map((header, index) => (
              <TableHead
                className={cn(
                  "break-all",
                  typeof header === "string" ? undefined : header.className
                )}
                key={index}
              >
                {typeof header === "string" ? header : header.label}
              </TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {data.map((item, index) => renderRow(item, index))}
        </TableBody>
      </Table>
    </Card>
  );
}
