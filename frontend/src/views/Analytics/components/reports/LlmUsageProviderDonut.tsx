import { Card, CardContent } from "@/components/card";
import { Skeleton } from "@/components/skeleton";
import { formatUsd } from "@/helpers/formatCurrency";
import { cn } from "@/helpers/utils";
import type { LlmUsageBreakdownItem } from "@/interfaces/llmUsage.interface";
import { analyticsFadeUpClass } from "../../constants/animations";

interface LlmUsageProviderDonutProps {
  items: LlmUsageBreakdownItem[];
  loading?: boolean;
}

const TOP_N = 8;
const OTHERS_KEY = "others";
const NEUTRAL_RAIL = "hsl(var(--muted-foreground) / 0.45)";

const RAIL_COLORS = [
  "hsl(var(--chart-1))",
  "hsl(var(--chart-2))",
  "hsl(var(--chart-3))",
  "hsl(var(--chart-1) / 0.6)",
  "hsl(var(--chart-2) / 0.6)",
  "hsl(var(--chart-3) / 0.6)",
  "hsl(var(--chart-1) / 0.35)",
  "hsl(var(--chart-2) / 0.35)",
];

const railColor = (item: LlmUsageBreakdownItem, index: number) =>
  item.key === "unknown" || item.key === OTHERS_KEY ? NEUTRAL_RAIL : RAIL_COLORS[index % RAIL_COLORS.length];

const formatShare = (pct: number) => (pct > 0 && pct < 1 ? "<1%" : `${Math.round(pct)}%`);

const railWidth = (pct: number) => `${Math.min(100, Math.max(pct > 0 ? 1.5 : 0, pct))}%`;

function aggregateOthers(rest: LlmUsageBreakdownItem[]): LlmUsageBreakdownItem {
  return rest.reduce<LlmUsageBreakdownItem>(
    (acc, i) => ({
      ...acc,
      cost_usd: acc.cost_usd + i.cost_usd,
      cost_is_partial: acc.cost_is_partial || i.cost_is_partial,
      total_tokens: acc.total_tokens + i.total_tokens,
      calls: acc.calls + i.calls,
      unpriced_calls: acc.unpriced_calls + i.unpriced_calls,
    }),
    {
      key: OTHERS_KEY,
      label: "Others",
      cost_usd: 0,
      cost_is_partial: false,
      total_tokens: 0,
      calls: 0,
      unpriced_calls: 0,
    }
  );
}

export function LlmUsageProviderDonut({ items, loading }: LlmUsageProviderDonutProps) {
  const ranked = [...items].sort((a, b) => b.cost_usd - a.cost_usd);
  const top = ranked.slice(0, TOP_N);
  const rest = ranked.slice(TOP_N);
  const restCost = rest.reduce((s, i) => s + i.cost_usd, 0);
  const rows = restCost > 0 ? [...top, aggregateOthers(rest)] : top;
  const total = ranked.reduce((s, i) => s + i.cost_usd, 0);
  const digits = total >= 1 ? 2 : 4;
  const only = rows.length === 1 ? rows[0] : undefined;

  return (
    <Card className={cn("bg-card dark:bg-zinc-900 shadow-sm", analyticsFadeUpClass)}>
      <CardContent className="pt-6">
        <div className="mb-4 flex items-baseline justify-between gap-3">
          <h3 className="text-sm font-semibold text-foreground">Cost by Provider</h3>
          {!loading && total > 0 && (
            <span className="text-xs text-muted-foreground">
              Total <span className="ml-0.5 font-semibold tabular-nums text-foreground">{formatUsd(total, digits)}</span>
            </span>
          )}
        </div>
        {loading ? (
          <div className="space-y-4">
            {[0, 1, 2, 3].map((i) => (
              <div key={i} className="space-y-2">
                <Skeleton className="h-3.5 w-full" />
                <Skeleton className="h-2 w-full rounded-full" />
              </div>
            ))}
          </div>
        ) : rows.length === 0 || total === 0 ? (
          <div className="flex h-40 items-center justify-center text-sm text-muted-foreground">
            No usage recorded for this period.
          </div>
        ) : (
          <>
            <ul className="space-y-4">
              {rows.map((row, i) => {
                const share = (row.cost_usd / total) * 100;
                return (
                  <li key={row.key} className="space-y-1.5">
                    <div className="flex items-baseline gap-2 text-sm">
                      <span className="min-w-0 flex-1 truncate font-medium text-foreground" title={row.label}>
                        {row.label}
                      </span>
                      <span className="shrink-0 text-xs tabular-nums text-muted-foreground">{formatShare(share)}</span>
                      <span className="shrink-0 font-semibold tabular-nums text-foreground">
                        {formatUsd(row.cost_usd, digits)}
                      </span>
                    </div>
                    <div
                      role="progressbar"
                      aria-label={`${row.label} share of LLM cost`}
                      aria-valuemin={0}
                      aria-valuemax={100}
                      aria-valuenow={Math.round(share)}
                      className="h-2 w-full overflow-hidden rounded-full bg-muted"
                    >
                      <div
                        className="h-full rounded-full"
                        style={{ width: railWidth(share), background: railColor(row, i) }}
                      />
                    </div>
                  </li>
                );
              })}
            </ul>
            {only && (
              <p className="mt-5 text-xs text-muted-foreground">
                {only.calls.toLocaleString()} calls · {only.total_tokens.toLocaleString()} tokens
              </p>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}
