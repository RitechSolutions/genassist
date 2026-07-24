import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { Card, CardContent } from "@/components/card";
import { CHART_SERIES_COLORS, chartTooltipStyle } from "@/constants/chartColors";
import { formatUsd } from "@/helpers/formatCurrency";
import type { LlmUsageBreakdownItem } from "@/interfaces/llmUsage.interface";

interface LlmUsageProviderDonutProps {
  items: LlmUsageBreakdownItem[];
  loading?: boolean;
}

const UNPRICED_COLOR = "#f59e0b";
const TOP_N = 8;

const colorOf = (item: { key: string }, i: number) =>
  item.key === "unknown" || item.key === "unattributed"
    ? UNPRICED_COLOR
    : CHART_SERIES_COLORS[i % CHART_SERIES_COLORS.length];

/** Donut of LLM cost split by provider, with a share/cost legend list */
export function LlmUsageProviderDonut({ items, loading }: LlmUsageProviderDonutProps) {
  const ranked = [...items].sort((a, b) => b.cost_usd - a.cost_usd);
  const top = ranked.slice(0, TOP_N);
  const rest = ranked.slice(TOP_N);
  const restCost = rest.reduce((s, i) => s + i.cost_usd, 0);
  const slices = [
    ...top,
    ...(restCost > 0 ? [{ key: "others", label: "Others", cost_usd: restCost } as LlmUsageBreakdownItem] : []),
  ];
  const total = ranked.reduce((s, i) => s + i.cost_usd, 0);

  return (
    <Card>
      <CardContent className="pt-6">
        <h3 className="mb-2 text-sm font-semibold text-foreground">Cost by Provider</h3>
        {loading ? (
          <div className="h-72 animate-pulse rounded-lg bg-muted/40" />
        ) : slices.length === 0 || total === 0 ? (
          <div className="flex h-72 items-center justify-center text-sm text-muted-foreground">
            No usage recorded for this period.
          </div>
        ) : (
          <div className="flex flex-col items-center gap-5 sm:flex-row sm:gap-4">
            <div className="relative h-40 w-40 shrink-0">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={slices}
                    dataKey="cost_usd"
                    nameKey="label"
                    cx="50%"
                    cy="50%"
                    innerRadius={52}
                    outerRadius={78}
                    paddingAngle={2}
                    strokeWidth={0}
                  >
                    {slices.map((s, i) => (
                      <Cell key={s.key} fill={colorOf(s, i)} />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={chartTooltipStyle}
                    formatter={(value: number, name: string) => [formatUsd(Number(value)), name]}
                  />
                </PieChart>
              </ResponsiveContainer>
              <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
                <span className="text-base font-bold tabular-nums text-foreground">{formatUsd(total)}</span>
                <span className="text-xs text-muted-foreground">Total</span>
              </div>
            </div>
            <ul className="w-full min-w-0 flex-1 space-y-2.5 text-sm">
              {slices.map((s, i) => (
                <li key={s.key} className="flex items-center gap-2 tabular-nums">
                  <span className="h-2.5 w-2.5 shrink-0 rounded-sm" style={{ background: colorOf(s, i) }} />
                  <span className="min-w-0 flex-1 truncate text-muted-foreground" title={s.label}>
                    {s.label}
                  </span>
                  <span className="shrink-0 text-xs text-muted-foreground">
                    {total > 0 ? `${((s.cost_usd / total) * 100).toFixed(0)}%` : "0%"}
                  </span>
                  <span className="shrink-0 font-semibold text-foreground">{formatUsd(s.cost_usd, 2)}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
