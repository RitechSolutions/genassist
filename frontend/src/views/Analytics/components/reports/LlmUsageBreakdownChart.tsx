import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Card, CardContent } from "@/components/card";
import { CHART_NEUTRALS, CHART_SERIES_COLORS, chartTooltipStyle } from "@/constants/chartColors";
import { formatUsd } from "@/helpers/formatCurrency";
import type { LlmUsageBreakdownItem } from "@/interfaces/llmUsage.interface";

interface LlmUsageBreakdownChartProps {
  items: LlmUsageBreakdownItem[];
  dimensionLabel: string;
  loading?: boolean;
}

const MAX_BARS = 12;

/** Horizontal bar chart of LLM cost per breakdown row, cycling the categorical palette */
export function LlmUsageBreakdownChart({ items, dimensionLabel, loading }: LlmUsageBreakdownChartProps) {
  const data = items.slice(0, MAX_BARS).map((i) => ({ label: i.label, cost: i.cost_usd }));

  return (
    <Card>
      <CardContent className="pt-6">
        <h3 className="mb-4 text-sm font-semibold text-foreground">Cost by {dimensionLabel}</h3>
        {loading ? (
          <div className="h-80 animate-pulse rounded-lg bg-muted/40" />
        ) : data.length === 0 ? (
          <div className="flex h-80 items-center justify-center text-sm text-muted-foreground">
            No usage recorded for this period.
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={Math.max(240, data.length * 34)}>
            <BarChart data={data} layout="vertical" margin={{ top: 4, right: 24, bottom: 4, left: 8 }}>
              <CartesianGrid horizontal={false} stroke={CHART_NEUTRALS.grid} />
              <XAxis
                type="number"
                tickFormatter={(v) => formatUsd(Number(v), 2)}
                stroke={CHART_NEUTRALS.axis}
                fontSize={12}
              />
              <YAxis
                type="category"
                dataKey="label"
                width={150}
                stroke={CHART_NEUTRALS.axis}
                fontSize={12}
              />
              <Tooltip
                contentStyle={chartTooltipStyle}
                cursor={{ fill: "rgba(0,0,0,0.04)" }}
                formatter={(v: number | string) => [formatUsd(Number(v)), "Cost"]}
              />
              <Bar dataKey="cost" radius={[0, 4, 4, 0]}>
                {data.map((_, i) => (
                  <Cell key={i} fill={CHART_SERIES_COLORS[i % CHART_SERIES_COLORS.length]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        )}
      </CardContent>
    </Card>
  );
}
