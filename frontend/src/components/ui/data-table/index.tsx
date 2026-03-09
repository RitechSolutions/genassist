import React, { useState, useEffect, useMemo } from "react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/table";
import { Card } from "@/components/card";
import { Loader2, ArrowUpDown, ArrowUp, ArrowDown } from "lucide-react";
import { PaginationBar } from "@/components/PaginationBar";
import { getPaginationMeta } from "@/helpers/pagination";
export interface Column<T> {
  header: React.ReactNode;
  key: string;
  cell: (item: T, index: number) => React.ReactNode;
  description?: string;
  sortable?: boolean;
  sortValue?: (item: T) => string | number;
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
  pageSize?: number;
  onRowClick?: (item: T) => void;
}

type SortDir = "asc" | "desc" | null;

export function DataTable<T extends { id?: string | number }>({
  data,
  columns,
  loading = false,
  error = null,
  searchQuery = "",
  emptyMessage = "No data available",
  notFoundMessage = "No results found",
  keyExtractor = (item: T) => item.id as string | number,
  pageSize,
  onRowClick,
}: DataTableProps<T>) {
  const [currentPage, setCurrentPage] = useState(1);
  const [sortKey, setSortKey] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<SortDir>(null);
  useEffect(() => {
    setCurrentPage(1);
  }, [data, sortKey, sortDir]);

  const handleSort = (col: Column<T>) => {
    if (!col.sortable) return;
    if (sortKey === col.key) {
      setSortDir((prev) => (prev === "asc" ? "desc" : prev === "desc" ? null : "asc"));
      if (sortDir === "desc") setSortKey(null);
    } else {
      setSortKey(col.key);
      setSortDir("asc");
    }
  };

  const processedData = useMemo(() => {
    const result = [...data];

    if (sortKey && sortDir) {
      const col = columns.find((c) => c.key === sortKey);
      result.sort((a, b) => {
        const va = col?.sortValue ? col.sortValue(a) : (a as any)[sortKey] ?? "";
        const vb = col?.sortValue ? col.sortValue(b) : (b as any)[sortKey] ?? "";
        const cmp = typeof va === "number" && typeof vb === "number"
          ? va - vb
          : String(va).localeCompare(String(vb));
        return sortDir === "asc" ? cmp : -cmp;
      });
    }

    return result;
  }, [data, sortKey, sortDir, columns]);

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

  const pagination = pageSize
    ? getPaginationMeta(processedData.length, pageSize, currentPage)
    : null;

  const visibleData = pagination
    ? processedData.slice(pagination.startIndex, pagination.endIndex)
    : processedData;

  const sortIcon = (col: Column<T>) => {
    if (!col.sortable) return null;
    if (sortKey !== col.key || sortDir === null)
      return <ArrowUpDown className="w-3 h-3 ml-1 text-muted-foreground/50 inline-block" />;
    return sortDir === "asc"
      ? <ArrowUp className="w-3 h-3 ml-1 text-zinc-600 inline-block" />
      : <ArrowDown className="w-3 h-3 ml-1 text-zinc-600 inline-block" />;
  };

  return (
    <Card>
      <Table>
        <TableHeader>
          <TableRow>
            {columns.map((column) => (
              <TableHead
                key={column.key}
                onClick={() => handleSort(column)}
                className={column.sortable ? "cursor-pointer select-none hover:text-zinc-900" : undefined}
              >
                {column.header}
                {sortIcon(column)}
              </TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {processedData.length === 0 ? (
            <TableRow>
              <TableCell colSpan={columns.length} className="text-center text-muted-foreground py-8">
                {notFoundMessage}
              </TableCell>
            </TableRow>
          ) : (
            visibleData.map((item, index) => (
              <TableRow
                key={keyExtractor(item)}
                onClick={onRowClick ? () => onRowClick(item) : undefined}
                className={onRowClick ? "cursor-pointer hover:bg-muted/60" : undefined}
              >
                {columns.map((column) => (
                  <TableCell key={`${keyExtractor(item)}-${column.key}`}>
                    {column.cell(item, index)}
                  </TableCell>
                ))}
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>

      {pagination && processedData.length > 0 && (
        <PaginationBar
          total={processedData.length}
          pageSize={pageSize!}
          currentPage={pagination.safePage}
          pageItemCount={visibleData.length}
          onPageChange={setCurrentPage}
        />
      )}
    </Card>
  );
}
