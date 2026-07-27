import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Card, CardContent } from "@/components/card";
import { Skeleton } from "@/components/skeleton";
import { CHART_NEUTRALS, CHART_SERIES_COLORS } from "@/constants/chartColors";
import { formatUsd } from "@/helpers/formatCurrency";
import { cn, formatChartDate } from "@/helpers/utils";
import type { LlmUsageTimeseriesItem } from "@/interfaces/llmUsage.interface";
import { analyticsFadeUpClass } from "../../constants/animations";

export type SpendMetric = "cost" | "tokens";

interface LlmUsageTimeseriesChartProps {
  items: LlmUsageTimeseriesItem[];
  loading?: boolean;
  metric: SpendMetric;
  onMetricChange: (metric: SpendMetric) => void;
}

const COST_COLOR = CHART_SERIES_COLORS[1];
const TOKEN_COLOR = CHART_SERIES_COLORS[3];
const METRICS: Array<{ value: SpendMetric; label: string }> = [
  { value: "cost", label: "Cost" },
  { value: "tokens", label: "Tokens" },
];

const PLOT_HEIGHT = "h-56 sm:h-64 lg:h-72";

const compactTokens = (v: number) =>
  v >= 1_000_000 ? `${(v / 1_000_000).toFixed(1)}M` : v >= 1_000 ? `${(v / 1_000).toFixed(1)}K` : `${v}`;

const costTickDigits = (peak: number) => (peak >= 1 ? 2 : peak >= 0.01 ? 3 : 4);

interface SpendTooltipProps {
  active?: boolean;
  label?: string;
  payload?: Array<{ value?: number | string }>;
  color: string;
  metricLabel: string;
  format: (value: number) => string;
}

function SpendTooltip({ active, label, payload, color, metricLabel, format }: SpendTooltipProps) {
  const raw = payload?.[0]?.value;
  if (!active || raw === undefined) return null;
  return (
    <div className="rounded-lg border border-border bg-card px-3 py-2 text-xs shadow-md">
      <p className="mb-1.5 font-semibold text-foreground">{label}</p>
      <div className="flex items-center gap-2">
        <span className="h-2 w-2 shrink-0 rounded-full" style={{ background: color }} />
        <span className="text-muted-foreground">{metricLabel}</span>
        <span className="ml-3 font-semibold tabular-nums text-foreground">{format(Number(raw))}</span>
      </div>
    </div>
  );
}

/** Daily LLM spend over time, toggled between cost and tokens */
export function LlmUsageTimeseriesChart({ items, loading, metric, onMetricChange }: LlmUsageTimeseriesChartProps) {
  const isCost = metric === "cost";
  const color = isCost ? COST_COLOR : TOKEN_COLOR;
  const data = items.map((i) => ({ date: formatChartDate(i.stat_date), value: isCost ? i.cost_usd : i.total_tokens }));
  const total = items.reduce((sum, i) => sum + (isCost ? i.cost_usd : i.total_tokens), 0);
  const peak = data.reduce((max, d) => Math.max(max, d.value), 0);
  const fmt = (v: number) => (isCost ? formatUsd(v) : v.toLocaleString());
  const fmtAverage = (v: number) => (isCost ? formatUsd(v) : Math.round(v).toLocaleString());
  const showStats = !loading && data.length > 0;

  return (
    <Card className={cn("bg-card dark:bg-zinc-900 shadow-sm", analyticsFadeUpClass)}>
      <CardContent className="pt-6">
        <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
          <div>
            <h3 className="text-sm font-semibold text-foreground">Spend Over Time</h3>
            {showStats && (
              <div className="mt-2 flex flex-wrap items-baseline gap-x-8 gap-y-2">
                <div>
                  <p className="text-xs text-muted-foreground">Total</p>
                  <p className="text-xl font-bold tabular-nums text-foreground">{fmt(total)}</p>
                </div>
                {data.length > 1 && (
                  <div title={`Average across the ${data.length} days with recorded usage`}>
                    <p className="text-xs text-muted-foreground">Daily average</p>
                    <p className="text-xl font-bold tabular-nums text-foreground">{fmtAverage(total / data.length)}</p>
                  </div>
                )}
              </div>
            )}
          </div>
          <div
            role="group"
            aria-label="Spend metric"
            className="inline-flex shrink-0 overflow-hidden rounded-md border border-border"
          >
            {METRICS.map((m) => (
              <button
                key={m.value}
                type="button"
                aria-pressed={metric === m.value}
                onClick={() => onMetricChange(m.value)}
                className={cn(
                  "px-3 py-1 text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring",
                  metric === m.value
                    ? "bg-primary/10 text-primary"
                    : "bg-background text-muted-foreground hover:text-foreground"
                )}
              >
                {m.label}
              </button>
            ))}
          </div>
        </div>
        {loading ? (
          <Skeleton className={cn("w-full rounded-lg", PLOT_HEIGHT)} />
        ) : data.length === 0 ? (
          <div className={cn("flex items-center justify-center text-sm text-muted-foreground", PLOT_HEIGHT)}>
            No usage recorded for this period.
          </div>
        ) : (
          <div className={cn("w-full", PLOT_HEIGHT)}>
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: -4 }}>
                <defs>
                  <linearGradient id="llm-spend-grad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={color} stopOpacity={0.22} />
                    <stop offset="100%" stopColor={color} stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid
                  strokeDasharray="4 4"
                  stroke={CHART_NEUTRALS.axis}
                  strokeOpacity={0.25}
                  vertical={false}
                />
                <XAxis
                  dataKey="date"
                  axisLine={false}
                  tickLine={false}
                  tick={{ fontSize: 11, fill: CHART_NEUTRALS.axis }}
                  dy={6}
                  interval="preserveStartEnd"
                  minTickGap={24}
                />
                <YAxis
                  axisLine={false}
                  tickLine={false}
                  tick={{ fontSize: 11, fill: CHART_NEUTRALS.axis }}
                  domain={[0, peak > 0 ? "auto" : 1]}
                  allowDecimals={isCost}
                  tickFormatter={(v) =>
                    isCost ? formatUsd(Number(v), costTickDigits(peak)) : compactTokens(Number(v))
                  }
                  width={isCost ? 64 : 48}
                />
                <Tooltip
                  cursor={{ stroke: CHART_NEUTRALS.axis, strokeOpacity: 0.45, strokeWidth: 1 }}
                  content={
                    <SpendTooltip color={color} metricLabel={isCost ? "Cost" : "Tokens"} format={fmt} />
                  }
                />
                <Area
                  type="monotone"
                  dataKey="value"
                  stroke={color}
                  strokeWidth={2}
                  // A lone point draws no line segment, so it needs a visible dot of its own
                  dot={data.length === 1 ? { r: 4, fill: color, strokeWidth: 0 } : false}
                  activeDot={{ r: 5, fill: color, strokeWidth: 0 }}
                  fill="url(#llm-spend-grad)"
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
