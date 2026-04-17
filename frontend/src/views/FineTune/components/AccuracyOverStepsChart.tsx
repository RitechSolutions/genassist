import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/card";
import { Skeleton } from "@/components/skeleton";

export interface StepDataPoint {
  label: string;
  value: number;
}

interface AccuracyOverStepsChartProps {
  data: StepDataPoint[];
  loading?: boolean;
  title?: string;
  valueLabel?: string;
  valueMode?: "percent" | "number";
  accentColor?: string;
}

const SERIES_KEY = "value";

function formatNumberTick(n: number): string {
  if (!isFinite(n)) return "—";
  const abs = Math.abs(n);
  if (abs >= 1000) return n.toExponential(1);
  if (abs >= 1) return n.toFixed(2);
  return n.toFixed(4);
}

export function AccuracyOverStepsChart({
  data,
  loading = false,
  title = "Accuracy over steps",
  valueLabel = "Accuracy",
  valueMode = "percent",
  accentColor,
}: AccuracyOverStepsChartProps) {
  if (loading) {
    return <Skeleton className="h-[320px] rounded-xl w-full" />;
  }

  const chartData = data.map((p) => ({ label: p.label, [SERIES_KEY]: p.value }));
  const latest = data.length > 0 ? data[data.length - 1].value : 0;
  const isPercent = valueMode === "percent";
  const stroke = accentColor ?? (isPercent ? "#10b981" : "#0d9488");
  const gradId = `grad-metric-over-steps-${isPercent ? "pct" : "num"}`;
  const values = data.map((d) => d.value).filter((v) => isFinite(v));
  const yMin = !isPercent && values.length ? Math.min(...values) : 0;
  const yMax = !isPercent && values.length ? Math.max(...values) : 100;
  const yPad =
    !isPercent && values.length
      ? Math.max((yMax - yMin) * 0.08, 1e-6)
      : 0;
  const yDomain: [number | string, number | string] = isPercent
    ? [0, 100]
    : [yMin - yPad, yMax + yPad];

  const latestDisplay = isPercent ? `${latest}%` : formatNumberTick(latest);

  return (
    <Card className="rounded-lg border text-card-foreground bg-white shadow-sm">
      <CardHeader className="pb-0">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <CardTitle className="text-sm font-semibold text-zinc-700">{title}</CardTitle>
          <div className="flex items-center gap-4 text-xs text-muted-foreground">
            <span className="flex items-center gap-1.5">
              <span
                className="w-2.5 h-2.5 rounded-full inline-block"
                style={{ backgroundColor: stroke }}
              />
              Steps
              <span className="font-semibold text-zinc-700 ml-0.5">{data.length}</span>
            </span>
            {data.length > 0 && (
              <span className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-full bg-teal-500 inline-block" />
                Latest
                <span className="font-semibold text-zinc-700 ml-0.5">{latestDisplay}</span>
              </span>
            )}
          </div>
        </div>
      </CardHeader>
      <CardContent className="pt-4">
        {chartData.length === 0 ? (
          <div className="flex items-center justify-center h-56 text-sm text-muted-foreground">
            No data available for the selected period.
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={240}>
            <AreaChart data={chartData} margin={{ top: 4, right: 4, bottom: 0, left: -8 }}>
              <defs>
                <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={stroke} stopOpacity={0.15} />
                  <stop offset="100%" stopColor={stroke} stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#f4f4f5" vertical={false} />
              <XAxis
                dataKey="label"
                axisLine={false}
                tickLine={false}
                tick={{ fontSize: 11, fill: "#a1a1aa" }}
                dy={6}
                interval={0}
                minTickGap={0}
              />
              <YAxis
                domain={yDomain}
                axisLine={false}
                tickLine={false}
                tick={{ fontSize: 11, fill: "#a1a1aa" }}
                allowDecimals={!isPercent}
                tickFormatter={(v) =>
                  isPercent ? `${v}%` : formatNumberTick(Number(v))
                }
              />
              <Tooltip
                contentStyle={{
                  background: "white",
                  border: "1px solid #e4e4e7",
                  borderRadius: "10px",
                  fontSize: "12px",
                  boxShadow: "0 4px 12px rgba(0,0,0,0.08)",
                }}
                cursor={{ stroke: "#e4e4e7", strokeWidth: 1 }}
                formatter={(value: number) =>
                  isPercent
                    ? [`${value}%`, valueLabel]
                    : [formatNumberTick(value), valueLabel]}
              />
              <Area
                type="monotone"
                dataKey={SERIES_KEY}
                stroke={stroke}
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 4, strokeWidth: 0 }}
                fill={`url(#${gradId})`}
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </CardContent>
    </Card>
  );
}
