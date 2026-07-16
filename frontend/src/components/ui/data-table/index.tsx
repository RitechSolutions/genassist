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
import { TableSkeleton } from "@/components/skeletons";
import { ArrowUpDown, ArrowUp, ArrowDown } from "lucide-react";
import { PaginationBar } from "@/components/PaginationBar";
import { getPaginationMeta } from "@/helpers/pagination";
import { cn } from "@/helpers/utils";
export interface Column<T> {
  header: React.ReactNode;
  key: string;
  /** `index` is the item's absolute position across all pages (1-based numbering: `index + 1`). */
  cell: (item: T, index: number) => React.ReactNode;
  description?: string;
  sortable?: boolean;
  sortValue?: (item: T) => string | number;
  /** Extra classes for this column's body `<TableCell>`. */
  className?: string;
  /** Extra classes for this column's header `<TableHead>`. */
  headerClassName?: string;
}

export interface DataTableProps<T> {
  data: T[];
  columns: Column<T>[];
  loading?: boolean;
  error?: string | null;
  searchQuery?: string;
  emptyMessage?: string;
  notFoundMessage?: string;
  /** Rich empty UI (e.g. ListEmptyState). Falls back to emptyMessage when omitted. */
  emptyState?: React.ReactNode;
  keyExtractor?: (item: T) => string | number;
  pageSize?: number;
  onRowClick?: (item: T) => void;
  /** When set, rows are clustered by this key so each group's items are consecutive. */
  groupBy?: (item: T) => string;
  /**
   * Renders a full-width header row above each group's first item. Receives the
   * group key and its items; return null/undefined to omit the header for that group.
   */
  renderGroupHeader?: (groupKey: string, items: T[]) => React.ReactNode;
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
  emptyState,
  keyExtractor = (item: T) => item.id as string | number,
  pageSize,
  onRowClick,
  groupBy,
  renderGroupHeader,
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

    // Cluster items so each group's rows are consecutive (stable, first-seen order).
    if (groupBy) {
      const map = new Map<string, T[]>();
      for (const item of result) {
        const k = groupBy(item);
        const arr = map.get(k);
        if (arr) arr.push(item);
        else map.set(k, [item]);
      }
      return Array.from(map.values()).flat();
    }

    return result;
  }, [data, sortKey, sortDir, columns, groupBy]);

  const groupItems = useMemo(() => {
    if (!groupBy) return null;
    const map = new Map<string, T[]>();
    for (const item of processedData) {
      const k = groupBy(item);
      const arr = map.get(k);
      if (arr) arr.push(item);
      else map.set(k, [item]);
    }
    return map;
  }, [processedData, groupBy]);

  if (loading) {
    return <TableSkeleton columns={columns.length} />;
  }

  if (error) {
    return (
      <Card className="p-8">
        <div className="text-center text-destructive">{error}</div>
      </Card>
    );
  }

  if (data.length === 0) {
    return (
      <Card className="overflow-hidden shadow-sm">
        {emptyState ?? (
          <div className="p-8">
            <div className="text-center text-muted-foreground">
              {searchQuery ? notFoundMessage : emptyMessage}
            </div>
          </div>
        )}
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

  const startIndex = pagination?.startIndex ?? 0;

  const renderItemRow = (item: T, absoluteIndex: number) => (
    <TableRow
      key={keyExtractor(item)}
      onClick={onRowClick ? () => onRowClick(item) : undefined}
      onKeyDown={
        onRowClick
          ? (e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                onRowClick(item);
              }
            }
          : undefined
      }
      tabIndex={onRowClick ? 0 : undefined}
      className={
        onRowClick
          ? "cursor-pointer hover:bg-muted/60 focus-within:bg-muted/60"
          : undefined
      }
    >
      {columns.map((column) => (
        <TableCell
          key={`${keyExtractor(item)}-${column.key}`}
          className={column.className}
        >
          {column.cell(item, absoluteIndex)}
        </TableCell>
      ))}
    </TableRow>
  );

  const renderRows = () => {
    if (!groupBy) {
      return visibleData.map((item, index) =>
        renderItemRow(item, startIndex + index)
      );
    }
    const nodes: React.ReactNode[] = [];
    let prevGroup: string | null = null;
    visibleData.forEach((item, index) => {
      const key = groupBy(item);
      if (key !== prevGroup) {
        prevGroup = key;
        const header = renderGroupHeader?.(key, groupItems?.get(key) ?? []);
        if (header != null && header !== false) {
          nodes.push(
            <TableRow
              key={`group-${key}`}
              className="bg-muted/40 hover:bg-muted/40 border-t-2 border-border"
            >
              <TableCell
                colSpan={columns.length}
                className="font-semibold text-foreground py-3"
              >
                {header}
              </TableCell>
            </TableRow>
          );
        }
      }
      nodes.push(renderItemRow(item, startIndex + index));
    });
    return nodes;
  };

  return (
    <>
      <Card>
      <Table>
        <TableHeader>
          <TableRow>
            {columns.map((column) => (
              <TableHead
                key={column.key}
                onClick={() => handleSort(column)}
                className={cn(
                  column.sortable && "cursor-pointer select-none hover:text-zinc-900",
                  column.headerClassName
                )}
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
            renderRows()
          )}
        </TableBody>
      </Table>
      </Card>

      {pagination && processedData.length > 0 && (
        <PaginationBar
          total={processedData.length}
          pageSize={pageSize!}
          currentPage={pagination.safePage}
          pageItemCount={visibleData.length}
          onPageChange={setCurrentPage}
        />
      )}
    </>
  );
}
