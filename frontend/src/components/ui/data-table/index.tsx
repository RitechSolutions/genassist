import React, { ReactNode } from "react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/table";
import { Card } from "@/components/card";
import { Loader2 } from "lucide-react";

export interface Column<T> {
  header: string;
  key: string;
  cell: (item: T, index: number) => React.ReactNode;
}

export interface DataTableProps<T> {
  data: T[];
  columns: Column<T>[];
  loading?: boolean;
  error?: string | null;
  searchQuery?: string;
  emptyMessage?: string;
  notFoundMessage?: string;
  keyExtractor?: (item: T) => string | number;
}

export function DataTable<T extends { id?: string | number }>({
  data,
  columns,
  loading = false,
  error = null,
  searchQuery = "",
  emptyMessage = "No data available",
  notFoundMessage = "No results found",
  keyExtractor = (item: T) => item.id as string | number
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
          {searchQuery ? notFoundMessage : emptyMessage}
        </div>
      </Card>
    );
  }

  return (
    <Card>
      <Table>
        <TableHeader>
          <TableRow>
            {columns.map((column) => (
              <TableHead key={column.key}>{column.header}</TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {data.map((item, index) => (
            <TableRow key={keyExtractor(item)}>
              {columns.map((column) => (
                <TableCell key={`${keyExtractor(item)}-${column.key}`}>
                  {column.cell(item, index)}
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Card>
  );
} 