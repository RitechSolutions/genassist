import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Card, CardContent } from "@/components/card";
import { CHART_NEUTRALS, CHART_SERIES_COLORS, chartTooltipCursor, chartTooltipStyle } from "@/constants/chartColors";
import { formatUsd } from "@/helpers/formatCurrency";
import { formatChartDate } from "@/helpers/utils";
import type { LlmUsageTimeseriesItem } from "@/interfaces/llmUsage.interface";

export type SpendMetric = "cost" | "tokens";

interface LlmUsageTimeseriesChartProps {
  items: LlmUsageTimeseriesItem[];
  loading?: boolean;
  metric: SpendMetric;
  onMetricChange: (metric: SpendMetric) => void;
}

const COST_COLOR = CHART_SERIES_COLORS[1];
const TOKEN_COLOR = CHART_SERIES_COLORS[0];
const METRICS: Array<{ value: SpendMetric; label: string }> = [
  { value: "cost", label: "Cost" },
  { value: "tokens", label: "Tokens" },
];

const compactTokens = (v: number) =>
  v >= 1_000_000 ? `${(v / 1_000_000).toFixed(1)}M` : v >= 1_000 ? `${(v / 1_000).toFixed(1)}K` : `${v}`;

/** Daily LLM spend over time, toggled between cost and tokens */
export function LlmUsageTimeseriesChart({ items, loading, metric, onMetricChange }: LlmUsageTimeseriesChartProps) {
  const isCost = metric === "cost";
  const color = isCost ? COST_COLOR : TOKEN_COLOR;
  const data = items.map((i) => ({ date: formatChartDate(i.stat_date), value: isCost ? i.cost_usd : i.total_tokens }));
  const total = items.reduce((sum, i) => sum + (isCost ? i.cost_usd : i.total_tokens), 0);
  const fmt = (v: number) => (isCost ? formatUsd(v) : v.toLocaleString());

  return (
    <Card>
      <CardContent className="pt-6">
        <div className="mb-4 flex items-center justify-between gap-3">
          <h3 className="text-sm font-semibold text-foreground">Spend Over Time</h3>
          <div className="flex items-center gap-3">
            <span className="hidden text-xs text-muted-foreground sm:inline">
              Total <span className="ml-0.5 font-semibold text-foreground">{fmt(total)}</span>
            </span>
            <div className="inline-flex overflow-hidden rounded-md border border-border">
              {METRICS.map((m) => (
                <button
                  key={m.value}
                  onClick={() => onMetricChange(m.value)}
                  className={`px-3 py-1 text-xs font-medium transition-colors ${
                    metric === m.value
                      ? "bg-primary/10 text-primary"
                      : "bg-background text-muted-foreground hover:text-foreground"
                  }`}
                >
                  {m.label}
                </button>
              ))}
            </div>
          </div>
        </div>
        {loading ? (
          <div className="h-72 animate-pulse rounded-lg bg-muted/40" />
        ) : data.length === 0 ? (
          <div className="flex h-72 items-center justify-center text-sm text-muted-foreground">
            No usage recorded for this period.
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={288}>
            <AreaChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: -4 }}>
              <defs>
                <linearGradient id="llm-spend-grad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={color} stopOpacity={0.18} />
                  <stop offset="100%" stopColor={color} stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke={CHART_NEUTRALS.grid} vertical={false} />
              <XAxis
                dataKey="date"
                axisLine={false}
                tickLine={false}
                tick={{ fontSize: 11, fill: CHART_NEUTRALS.axis }}
                dy={6}
              />
              <YAxis
                axisLine={false}
                tickLine={false}
                tick={{ fontSize: 11, fill: CHART_NEUTRALS.axis }}
                tickFormatter={(v) => (isCost ? formatUsd(Number(v), 2) : compactTokens(Number(v)))}
                width={isCost ? 64 : 48}
              />
              <Tooltip
                contentStyle={chartTooltipStyle}
                cursor={chartTooltipCursor}
                formatter={(value: number | string) => [fmt(Number(value)), isCost ? "Cost" : "Tokens"]}
              />
              <Area
                type="monotone"
                dataKey="value"
                stroke={color}
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 4, strokeWidth: 0 }}
                fill="url(#llm-spend-grad)"
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </CardContent>
    </Card>
  );
}
