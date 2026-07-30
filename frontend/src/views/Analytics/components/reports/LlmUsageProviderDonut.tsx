import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { Card, CardContent } from "@/components/card";
import { Skeleton } from "@/components/skeleton";
import { CHART_NEUTRALS, CHART_SERIES_COLORS } from "@/constants/chartColors";
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
const RING_HEIGHT = "h-52";
// Four rows plus a peek at the next: the card keeps its height no matter how many providers appear
const TABLE_MAX_HEIGHT = "max-h-40";
const NUM_HEAD = "py-1.5 pl-3 text-right font-medium";
const NUM_CELL = "py-1.5 pl-3 text-right tabular-nums text-muted-foreground";

const sliceColor = (item: LlmUsageBreakdownItem, index: number) =>
  item.key === "unknown" || item.key === OTHERS_KEY
    ? CHART_NEUTRALS.axis
    : CHART_SERIES_COLORS[index % CHART_SERIES_COLORS.length];

const formatShare = (pct: number) => (pct > 0 && pct < 1 ? "<1%" : `${Math.round(pct)}%`);

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

interface ProviderSliceTooltipProps {
  active?: boolean;
  payload?: Array<{ payload: LlmUsageBreakdownItem }>;
  total: number;
  digits: number;
}

function ProviderSliceTooltip({ active, payload, total, digits }: ProviderSliceTooltipProps) {
  const row = payload?.[0]?.payload;
  if (!active || !row) return null;
  const stats: Array<[string, string]> = [
    ["Cost", formatUsd(row.cost_usd, digits)],
    ["Tokens", row.total_tokens.toLocaleString()],
    ["Share", total > 0 ? formatShare((row.cost_usd / total) * 100) : "—"],
  ];
  return (
    <div className="rounded-lg border border-border bg-card px-3 py-2 text-xs shadow-md">
      <p className="mb-1.5 font-semibold text-foreground">{row.label}</p>
      <dl className="space-y-0.5">
        {stats.map(([term, value]) => (
          <div key={term} className="flex items-baseline gap-4">
            <dt className="text-muted-foreground">{term}</dt>
            <dd className="ml-auto font-semibold tabular-nums text-foreground">{value}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

/** Provider share of LLM spend: donut plus the per-provider detail it is drawn from */
export function LlmUsageProviderDonut({ items, loading }: LlmUsageProviderDonutProps) {
  const ranked = [...items].sort((a, b) => b.cost_usd - a.cost_usd);
  const top = ranked.slice(0, TOP_N);
  const rest = ranked.slice(TOP_N);
  // Providers past the top eight can be unpriced yet still have calls and tokens, so Others follows row count, not cost
  const rows = rest.length > 0 ? [...top, aggregateOthers(rest)] : top;
  const total = ranked.reduce((s, i) => s + i.cost_usd, 0);
  const digits = total >= 1 ? 2 : 4;
  const priced = total > 0;

  return (
    <Card className={cn("bg-card dark:bg-zinc-900 shadow-sm", analyticsFadeUpClass)}>
      <CardContent className="pt-6">
        <h3 className="mb-4 text-sm font-semibold text-foreground">Cost by Provider</h3>
        {loading ? (
          <div className="space-y-4">
            <div className={cn("flex items-center justify-center", RING_HEIGHT)}>
              <Skeleton className="h-44 w-44 rounded-full" />
            </div>
            {[0, 1, 2, 3].map((i) => (
              <Skeleton key={i} className="h-3.5 w-full" />
            ))}
          </div>
        ) : rows.length === 0 ? (
          <div className="flex h-40 items-center justify-center text-sm text-muted-foreground">
            No usage recorded for this period.
          </div>
        ) : (
          <>
            <div className={cn("relative", RING_HEIGHT)}>
              {/* The table below is the accessible representation of these slices */}
              <div className="absolute inset-0" aria-hidden>
                {priced ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={rows}
                        dataKey="cost_usd"
                        nameKey="label"
                        cx="50%"
                        cy="50%"
                        innerRadius={60}
                        outerRadius={90}
                        paddingAngle={2}
                        strokeWidth={0}
                        minAngle={2}
                        rootTabIndex={-1}
                      >
                        {rows.map((row, i) => (
                          <Cell key={row.key} fill={sliceColor(row, i)} />
                        ))}
                      </Pie>
                      {/* Recharts anchors pie tooltips on the arc itself; pinning y keeps it off the ring */}
                      <Tooltip
                        content={<ProviderSliceTooltip total={total} digits={digits} />}
                        position={{ y: 0 }}
                        wrapperStyle={{ zIndex: 10 }}
                      />
                    </PieChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="flex h-full items-center justify-center">
                    <div className="h-[180px] w-[180px] rounded-full border-[30px] border-muted" />
                  </div>
                )}
              </div>
              <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
                <span className="text-[11px] uppercase tracking-wide text-muted-foreground">Total</span>
                <span className="text-lg font-bold tabular-nums text-foreground">{formatUsd(total, digits)}</span>
                {!priced && <span className="mt-0.5 text-[11px] text-muted-foreground">no priced spend</span>}
              </div>
            </div>
            <div className={cn("mt-4 overflow-auto", TABLE_MAX_HEIGHT)}>
              <table className="w-full min-w-[20rem] text-xs">
                <thead className="sticky top-0 z-10 bg-card dark:bg-zinc-900">
                  <tr className="border-b border-border text-muted-foreground">
                    <th className="py-1.5 text-left font-medium">Provider</th>
                    <th className={NUM_HEAD}>Calls</th>
                    <th className={NUM_HEAD}>Tokens</th>
                    <th className={NUM_HEAD}>Cost</th>
                    <th className={NUM_HEAD}>Share</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row, i) => (
                    <tr key={row.key} className="border-b border-border/50 last:border-0">
                      <td className="py-1.5">
                        <span className="flex items-center gap-1.5">
                          <span
                            className="h-2 w-2 shrink-0 rounded-full"
                            style={{ background: sliceColor(row, i) }}
                          />
                          <span className="max-w-[9rem] truncate font-medium text-foreground" title={row.label}>
                            {row.label}
                          </span>
                        </span>
                      </td>
                      <td className={NUM_CELL}>{row.calls.toLocaleString()}</td>
                      <td className={NUM_CELL}>{row.total_tokens.toLocaleString()}</td>
                      <td className="py-1.5 pl-3 text-right font-semibold tabular-nums text-foreground">
                        {formatUsd(row.cost_usd, digits)}
                        {row.cost_is_partial && <span className="ml-1 font-normal text-amber-500">partial</span>}
                      </td>
                      <td className={NUM_CELL}>{priced ? formatShare((row.cost_usd / total) * 100) : "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
