import { Skeleton } from "@/components/skeleton";
import { TableCell, TableRow } from "@/components/table";
import { formatUsd } from "@/helpers/formatCurrency";
import type { LlmUsageBreakdownItem } from "@/interfaces/llmUsage.interface";

import { LlmUsageCostShare } from "./LlmUsageCostShare";

interface LlmUsageEvaluationMethodsProps {
  items: LlmUsageBreakdownItem[];
  totalCostUsd: number;
  loading?: boolean;
  error?: boolean;
}

// Matches the Usage by Type column count so status rows span the full table
const PARENT_COLUMNS = 6;
const ROW_CLASS = "bg-muted/20 hover:bg-muted/20";

/** Splits the Evaluations row into its methods as subordinate rows of the same table */
export function LlmUsageEvaluationMethods({ items, totalCostUsd, loading, error }: LlmUsageEvaluationMethodsProps) {
  if (error) {
    return (
      <TableRow className={ROW_CLASS}>
        <TableCell colSpan={PARENT_COLUMNS} className="py-2 pl-10 text-xs text-destructive">
          Failed to load evaluation breakdown.
        </TableCell>
      </TableRow>
    );
  }

  if (loading) {
    return (
      <TableRow className={ROW_CLASS}>
        <TableCell colSpan={PARENT_COLUMNS} className="py-2 pl-10">
          <Skeleton className="h-4 w-full" />
        </TableCell>
      </TableRow>
    );
  }

  if (items.length === 0) {
    return (
      <TableRow className={ROW_CLASS}>
        <TableCell colSpan={PARENT_COLUMNS} className="py-2 pl-10 text-xs text-muted-foreground">
          No evaluation LLM spend in this period.
        </TableCell>
      </TableRow>
    );
  }

  return (
    <>
      {items.map((item) => (
        <TableRow key={item.key} className={ROW_CLASS}>
          <TableCell className="py-2">
            <div className="flex items-center gap-2 pl-6">
              <span aria-hidden className="h-3 w-3 -translate-y-1 border-b border-l border-border" />
              <span className="font-medium">{item.label}</span>
            </div>
          </TableCell>
          <TableCell className="py-2">
            <span className="tabular-nums">{item.calls.toLocaleString()}</span>
          </TableCell>
          <TableCell className="py-2">
            <span className="tabular-nums">{item.total_tokens.toLocaleString()}</span>
          </TableCell>
          <TableCell className="py-2">
            <span className="tabular-nums font-semibold">{formatUsd(item.cost_usd)}</span>
          </TableCell>
          <TableCell className="py-2">
            <span className="tabular-nums text-muted-foreground">
              {formatUsd(item.calls ? item.cost_usd / item.calls : 0)}
            </span>
          </TableCell>
          <TableCell className="py-2">
            <LlmUsageCostShare costUsd={item.cost_usd} totalCostUsd={totalCostUsd} />
          </TableCell>
        </TableRow>
      ))}
    </>
  );
}
