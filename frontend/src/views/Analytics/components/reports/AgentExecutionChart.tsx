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
import { AnalyticsChartCardSkeleton } from "@/components/skeletons";
import { DailyConversationsChartEmptyState } from "../AnalyticsEmptyStates";
import { analyticsFadeUpClass } from "../../constants/animations";
import { cn, formatChartDate } from "@/helpers/utils";
import {
  CHART_SERIES_COLORS,
  CHART_NEUTRALS,
  chartTooltipStyle,
  chartTooltipCursor,
} from "@/constants/chartColors";
import type { AgentDailyStatsItem } from "@/interfaces/analyticsReports.interface";

interface AgentExecutionChartProps {
  items: AgentDailyStatsItem[];
  loading: boolean;
  agentNameMap: Record<string, string>;
}

const COLORS = CHART_SERIES_COLORS;


export function AgentExecutionChart({ items, loading, agentNameMap }: AgentExecutionChartProps) {
  if (loading) {
    return <AnalyticsChartCardSkeleton variant="area" />;
  }

  const dateSet = new Set<string>();
  const agentSet = new Set<string>();
  for (const item of items) {
    dateSet.add(item.stat_date);
    agentSet.add(item.agent_id);
  }
  const dates = Array.from(dateSet).sort();
  const agentIds = Array.from(agentSet);

  const pivot = new Map<string, Record<string, number>>();
  for (const date of dates) {
    const row: Record<string, number> = {};
    for (const agentId of agentIds) {
      row[agentId] = 0;
    }
    pivot.set(date, row);
  }
  for (const item of items) {
    pivot.get(item.stat_date)![item.agent_id] = item.unique_conversations;
  }

  const data = dates.map((date) => ({
    date: formatChartDate(date),
    ...pivot.get(date),
  }));

  const totalConversations = items.reduce((s, i) => s + i.unique_conversations, 0);

  return (
    <Card className={cn("bg-white shadow-sm", analyticsFadeUpClass)}>
      <CardHeader className="pb-0">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <CardTitle className="text-sm font-semibold text-zinc-700">
            Daily Conversations
          </CardTitle>
          <div className="flex items-center gap-4 text-xs text-muted-foreground">
            <span className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 inline-block" />
              Total
              <span className="font-semibold text-zinc-700 ml-0.5">{totalConversations.toLocaleString()}</span>
            </span>
          </div>
        </div>
      </CardHeader>
      <CardContent className="pt-4">
        {data.length === 0 ? (
          <DailyConversationsChartEmptyState />
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
                allowDecimals={false}
              />
              <Tooltip
                contentStyle={chartTooltipStyle}
                cursor={chartTooltipCursor}
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
