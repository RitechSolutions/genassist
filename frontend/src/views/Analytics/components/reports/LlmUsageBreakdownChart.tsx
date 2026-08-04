import { Card, CardContent } from "@/components/card";
import { Skeleton } from "@/components/skeleton";
import { formatUsd } from "@/helpers/formatCurrency";
import { cn } from "@/helpers/utils";
import type { LlmUsageBreakdownItem } from "@/interfaces/llmUsage.interface";
import { analyticsFadeUpClass } from "../../constants/animations";
import { LlmNodeCostChartEmptyState } from "../AnalyticsEmptyStates";

interface LlmUsageBreakdownChartProps {
  items: LlmUsageBreakdownItem[];
  dimensionLabel: string;
  loading?: boolean;
  error?: string | null;
  scopeNote?: string;
}

const MAX_ROWS = 12;

const railColor = (index: number) => `hsl(var(--chart-1) / ${Math.max(0.4, 1 - index * 0.06).toFixed(2)})`;

const formatShare = (pct: number) => (pct > 0 && pct < 1 ? "<1%" : `${Math.round(pct)}%`);

const railWidth = (pct: number) => `${Math.min(100, Math.max(pct > 0 ? 1.5 : 0, pct))}%`;

export function LlmUsageBreakdownChart({
  items,
  dimensionLabel,
  loading,
  error = null,
  scopeNote,
}: LlmUsageBreakdownChartProps) {
  const rows = items.slice(0, MAX_ROWS);
  const total = items.reduce((sum, i) => sum + i.cost_usd, 0);
  const peak = rows.reduce((max, i) => Math.max(max, i.cost_usd), 0);
  const digits = peak >= 1 ? 2 : 4;

  return (
    <Card className={cn("bg-card dark:bg-zinc-900 shadow-sm", analyticsFadeUpClass)}>
      <CardContent className="pt-6">
        <div className="mb-5 flex flex-wrap items-baseline justify-between gap-3">
          <h3 className="text-sm font-semibold text-foreground">Cost by {dimensionLabel}</h3>
          <div className="flex items-baseline gap-4 text-xs text-muted-foreground">
            {items.length > MAX_ROWS && (
              <span>
                Top {MAX_ROWS} of {items.length}
              </span>
            )}
            {!loading && !error && rows.length > 0 && (
              <span>
                Total{" "}
                <span className="ml-0.5 font-semibold tabular-nums text-foreground">{formatUsd(total, digits)}</span>
              </span>
            )}
          </div>
        </div>
        {scopeNote && <p className="-mt-3 mb-4 text-xs text-muted-foreground">{scopeNote}</p>}
        {loading ? (
          <div className="space-y-4">
            {[0, 1, 2, 3, 4, 5].map((i) => (
              <div key={i} className="flex items-center gap-4">
                <Skeleton className="h-3.5 w-40 shrink-0" />
                <Skeleton className="h-2 flex-1 rounded-full" />
                <Skeleton className="h-3.5 w-24 shrink-0" />
              </div>
            ))}
          </div>
        ) : error ? (
          <div className="flex h-40 items-center justify-center text-sm text-destructive">{error}</div>
        ) : rows.length === 0 ? (
          <LlmNodeCostChartEmptyState />
        ) : (
          <>
            <ul className="space-y-3.5">
              {rows.map((item, i) => {
                const share = total > 0 ? (item.cost_usd / total) * 100 : 0;
                const fill = peak > 0 ? (item.cost_usd / peak) * 100 : 0;
                return (
                  <li
                    key={item.key}
                    className="grid grid-cols-[1.25rem_minmax(0,1fr)_auto] items-center gap-x-3 gap-y-2 sm:grid-cols-[1.25rem_minmax(0,13rem)_minmax(0,1fr)_auto] sm:gap-x-4"
                  >
                    <span className="col-start-1 row-start-1 text-xs tabular-nums text-muted-foreground">{i + 1}</span>
                    <span
                      className="col-start-2 row-start-1 truncate text-sm font-medium text-foreground"
                      title={item.label}
                    >
                      {item.label}
                    </span>
                    <div className="col-start-3 row-start-1 flex shrink-0 items-baseline justify-end gap-2 sm:col-start-4">
                      {/* Muted, not amber: it explains history rather than warning about the number */}
                      {item.removed && <span className="text-xs text-muted-foreground">removed</span>}
                      <span className="text-sm font-semibold tabular-nums text-foreground">
                        {formatUsd(item.cost_usd, digits)}
                      </span>
                      <span className="w-10 text-right text-xs tabular-nums text-muted-foreground">
                        {formatShare(share)}
                      </span>
                    </div>
                    <div
                      role="progressbar"
                      aria-label={`${item.label} share of LLM cost`}
                      aria-valuemin={0}
                      aria-valuemax={100}
                      aria-valuenow={Math.round(share)}
                      className="col-span-2 col-start-2 row-start-2 h-2 overflow-hidden rounded-full bg-muted sm:col-span-1 sm:col-start-3 sm:row-start-1"
                    >
                      <div className="h-full rounded-full" style={{ width: railWidth(fill), background: railColor(i) }} />
                    </div>
                  </li>
                );
              })}
            </ul>
            {rows.length === 1 && total > 0 && (
              <p className="mt-5 text-xs text-muted-foreground">
                All recorded cost came from a single {dimensionLabel.toLowerCase()}.
              </p>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}
