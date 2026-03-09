import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/card";
import { Skeleton } from "@/components/skeleton";
import type { AgentDailyStatsItem } from "@/interfaces/analyticsReports.interface";

interface AgentExecutionChartProps {
  items: AgentDailyStatsItem[];
  loading: boolean;
  agentNameMap: Record<string, string>;
}

const COLORS = [
  "#10b981", "#3b82f6", "#f59e0b", "#8b5cf6", "#ef4444",
  "#06b6d4", "#f97316", "#84cc16", "#ec4899", "#14b8a6",
];

function formatDate(dateStr: string): string {
  const d = new Date(dateStr + "T00:00:00");
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

export function AgentExecutionChart({ items, loading, agentNameMap }: AgentExecutionChartProps) {
  if (loading) {
    return <Skeleton className="h-[320px] rounded-xl w-full" />;
  }

  // Collect unique sorted dates and unique agent IDs
  const dateSet = new Set<string>();
  const agentSet = new Set<string>();
  for (const item of items) {
    dateSet.add(item.stat_date);
    agentSet.add(item.agent_id);
  }
  const dates = Array.from(dateSet).sort();
  const agentIds = Array.from(agentSet);

  // Pivot: { date, [agentId]: successCount }
  const pivot = new Map<string, Record<string, number>>();
  for (const date of dates) {
    const row: Record<string, number> = {};
    for (const agentId of agentIds) {
      row[agentId] = 0;
    }
    pivot.set(date, row);
  }
  for (const item of items) {
    pivot.get(item.stat_date)![item.agent_id] = item.success_count;
  }

  const data = dates.map((date) => ({
    date: formatDate(date),
    ...pivot.get(date),
  }));

  const totalSuccess = items.reduce((s, i) => s + i.success_count, 0);
  const totalErrors = items.reduce((s, i) => s + i.error_count, 0);

  return (
    <Card className="bg-white shadow-sm">
      <CardHeader className="pb-0">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <CardTitle className="text-sm font-semibold text-zinc-700">
            Daily Execution Trend
          </CardTitle>
          <div className="flex items-center gap-4 text-xs text-muted-foreground">
            <span className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 inline-block" />
              Success
              <span className="font-semibold text-zinc-700 ml-0.5">{totalSuccess.toLocaleString()}</span>
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-red-400 inline-block" />
              Errors
              <span className="font-semibold text-zinc-700 ml-0.5">{totalErrors.toLocaleString()}</span>
            </span>
          </div>
        </div>
      </CardHeader>
      <CardContent className="pt-4">
        {data.length === 0 ? (
          <div className="flex items-center justify-center h-56 text-sm text-muted-foreground">
            No data available for the selected period.
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={agentIds.length > 1 ? 280 : 240}>
            <AreaChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: -8 }}>
              <defs>
                {agentIds.map((agentId, i) => {
                  const color = COLORS[i % COLORS.length];
                  return (
                    <linearGradient key={agentId} id={`grad-${agentId}`} x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor={color} stopOpacity={0.15} />
                      <stop offset="100%" stopColor={color} stopOpacity={0} />
                    </linearGradient>
                  );
                })}
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
                formatter={(value: number, agentId: string) => [
                  value.toLocaleString(),
                  agentNameMap[agentId] ?? agentId.slice(0, 8) + "…",
                ]}
              />
              {agentIds.length > 1 && (
                <Legend
                  formatter={(agentId) => agentNameMap[agentId] ?? agentId.slice(0, 8) + "…"}
                  wrapperStyle={{ fontSize: "11px", paddingTop: "8px" }}
                />
              )}
              {agentIds.map((agentId, i) => {
                const color = COLORS[i % COLORS.length];
                // Only show gradient fill for single agent; lines-only for multiple to avoid overlap
                const showFill = agentIds.length === 1;
                return (
                  <Area
                    key={agentId}
                    type="monotone"
                    dataKey={agentId}
                    stroke={color}
                    strokeWidth={2}
                    dot={false}
                    activeDot={{ r: 4, strokeWidth: 0 }}
                    fill={showFill ? `url(#grad-${agentId})` : "transparent"}
                  />
                );
              })}
            </AreaChart>
          </ResponsiveContainer>
        )}
      </CardContent>
    </Card>
  );
}
