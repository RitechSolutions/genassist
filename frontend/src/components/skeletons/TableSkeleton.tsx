import { Skeleton } from "@/components/skeleton";
import { Card } from "@/components/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/table";
import { cn } from "@/helpers/utils";

export interface TableSkeletonProps {
  columns: number;
  rows?: number;
  className?: string;
}

export function TableSkeleton({
  columns,
  rows = 5,
  className,
}: TableSkeletonProps) {
  return (
    <Card className={cn("overflow-hidden", className)}>
      <Table>
        <TableHeader>
          <TableRow>
            {Array.from({ length: columns }, (_, i) => (
              <TableHead key={i}>
                <Skeleton className="h-4 w-20" />
              </TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {Array.from({ length: rows }, (_, rowIndex) => (
            <TableRow key={rowIndex}>
              {Array.from({ length: columns }, (_, colIndex) => (
                <TableCell key={colIndex}>
                  <Skeleton
                    className={cn(
                      "h-4",
                      colIndex === 0 ? "w-32" : "w-24"
                    )}
                  />
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Card>
  );
}
