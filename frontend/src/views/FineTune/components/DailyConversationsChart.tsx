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

export interface JobEventWithDate {
  created_at?: string;
  metrics?: Record<string, unknown>;
}

interface DailyConversationsChartProps {
  events: JobEventWithDate[] | undefined;
  loading?: boolean;
  /** Optional label for the single series (e.g. "Training" or "Events"). Default "Activity". */
  seriesName?: string;
}

const SERIES_KEY = "count";

function formatDate(dateStr: string): string {
  const d = new Date(dateStr + "T00:00:00");
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

function getDateKey(createdAt: string | undefined): string | null {
  if (!createdAt) return null;
  const d = new Date(createdAt);
  if (isNaN(d.getTime())) return null;
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

export function DailyConversationsChart({
  events,
  loading = false,
  seriesName = "Activity",
}: DailyConversationsChartProps) {
  if (loading) {
    return <Skeleton className="h-[320px] rounded-xl w-full" />;
  }

  const dayCounts = new Map<string, number>();
  for (const e of events ?? []) {
    const key = getDateKey(e.created_at);
    if (key) {
      dayCounts.set(key, (dayCounts.get(key) ?? 0) + 1);
    }
  }
  const dates = Array.from(dayCounts.keys()).sort();
  const data = dates.map((date) => ({
    date: formatDate(date),
    [SERIES_KEY]: dayCounts.get(date) ?? 0,
  }));
  const total = (events ?? []).length;

  return (
    <Card className="bg-white shadow-sm">
      <CardHeader className="pb-0">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <CardTitle className="text-sm font-semibold text-zinc-700">
            Daily Conversations
          </CardTitle>
          <div className="flex items-center gap-4 text-xs text-muted-foreground">
            <span className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 inline-block" />
              Total
              <span className="font-semibold text-zinc-700 ml-0.5">{total.toLocaleString()}</span>
            </span>
          </div>
        </div>
      </CardHeader>
      <CardContent className="pt-4">
        {data.length === 0 ? (
          <div className="flex items-center justify-center h-56 text-sm text-muted-foreground">
            No data available.
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={240}>
            <AreaChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: -8 }}>
              <defs>
                <linearGradient id="grad-daily-job" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#10b981" stopOpacity={0.15} />
                  <stop offset="100%" stopColor="#10b981" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#f4f4f5" vertical={false} />
              <XAxis
                dataKey="date"
                axisLine={false}
                tickLine={false}
                tick={{ fontSize: 11, fill: "#a1a1aa" }}
                dy={6}
              />
              <YAxis
                axisLine={false}
                tickLine={false}
                tick={{ fontSize: 11, fill: "#a1a1aa" }}
                allowDecimals={false}
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
                formatter={(value: number) => [value.toLocaleString(), seriesName]}
              />
              <Area
                type="monotone"
                dataKey={SERIES_KEY}
                stroke="#10b981"
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 4, strokeWidth: 0 }}
                fill="url(#grad-daily-job)"
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </CardContent>
    </Card>
  );
}
