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
}

const SERIES_KEY = "value";

export function AccuracyOverStepsChart({
  data,
  loading = false,
  title = "Accuracy over steps",
  valueLabel = "Accuracy",
}: AccuracyOverStepsChartProps) {
  if (loading) {
    return <Skeleton className="h-[320px] rounded-xl w-full" />;
  }

  const chartData = data.map((p) => ({ label: p.label, [SERIES_KEY]: p.value }));
  const latest = data.length > 0 ? data[data.length - 1].value : 0;

  return (
    <Card className="rounded-lg border text-card-foreground bg-white shadow-sm">
      <CardHeader className="pb-0">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <CardTitle className="text-sm font-semibold text-zinc-700">{title}</CardTitle>
          <div className="flex items-center gap-4 text-xs text-muted-foreground">
            <span className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 inline-block" />
              Steps
              <span className="font-semibold text-zinc-700 ml-0.5">{data.length}</span>
            </span>
            {data.length > 0 && (
              <span className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-full bg-teal-500 inline-block" />
                Latest
                <span className="font-semibold text-zinc-700 ml-0.5">{latest}%</span>
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
                <linearGradient id="grad-accuracy-over-steps" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#10b981" stopOpacity={0.15} />
                  <stop offset="100%" stopColor="#10b981" stopOpacity={0} />
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
                domain={[0, 100]}
                axisLine={false}
                tickLine={false}
                tick={{ fontSize: 11, fill: "#a1a1aa" }}
                allowDecimals={false}
                tickFormatter={(v) => `${v}%`}
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
                formatter={(value: number) => [`${value}%`, valueLabel]}
              />
              <Area
                type="monotone"
                dataKey={SERIES_KEY}
                stroke="#10b981"
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 4, strokeWidth: 0 }}
                fill="url(#grad-accuracy-over-steps)"
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </CardContent>
    </Card>
  );
}
