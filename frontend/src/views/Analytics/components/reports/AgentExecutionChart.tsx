import { useMemo } from "react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
  type TooltipProps,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/card";
import { AnalyticsChartCardSkeleton } from "@/components/skeletons";
import { DailyConversationsChartEmptyState } from "../AnalyticsEmptyStates";
import { PeriodComparisonChartHint } from "./PeriodComparisonChartHint";
import { analyticsFadeUpClass } from "../../constants/animations";
import { cn } from "@/helpers/utils";
import { buildComparisonChartData } from "@/helpers/analyticsPeriodComparison";
import {
  compareLegendLabel,
  compareSeriesKey,
  formatChartDayLabel,
  formatPeriodRangeLabel,
  isCompareSeriesKey,
  normalizeDateKey,
} from "@/helpers/alignChartPeriods";
import type { AgentDailyStatsItem } from "@/interfaces/analyticsReports.interface";
import type { DateRange } from "react-day-picker";

interface AgentExecutionChartProps {
  items: AgentDailyStatsItem[];
  compareItems?: AgentDailyStatsItem[];
  dateRange?: DateRange;
  comparisonRange?: DateRange;
  comparedWithLabel?: string | null;
  loading: boolean;
  agentNameMap: Record<string, string>;
}

const COLORS = [
  "#10b981", "#3b82f6", "#f59e0b", "#8b5cf6", "#ef4444",
  "#06b6d4", "#f97316", "#84cc16", "#ec4899", "#14b8a6",
];

type ChartRow = {
  date: string;
  name: string;
  selectedDate: string;
  comparisonDate: string | null;
  [agentKey: string]: string | number | null;
};

function indexConversationsByDateAndAgent(items: AgentDailyStatsItem[]): Map<string, number> {
  const map = new Map<string, number>();
  for (const item of items) {
    map.set(`${normalizeDateKey(item.stat_date)}:${item.agent_id}`, item.unique_conversations);
  }
  return map;
}

function buildChartData(
  items: AgentDailyStatsItem[],
  compareItems: AgentDailyStatsItem[] | undefined,
  selectedRange: DateRange | undefined,
  comparisonRange: DateRange | undefined,
): { data: ChartRow[]; agentIds: string[] } {
  const agentSet = new Set<string>();
  for (const item of items) agentSet.add(item.agent_id);
  for (const item of compareItems ?? []) agentSet.add(item.agent_id);
  const agentIds = Array.from(agentSet);

  if (!selectedRange?.from || !selectedRange?.to) {
    return { data: [], agentIds };
  }

  const selectedByKey = indexConversationsByDateAndAgent(items);
  const compareByKey = compareItems ? indexConversationsByDateAndAgent(compareItems) : null;

  const comparing = Boolean(comparisonRange?.from && comparisonRange?.to && compareByKey);

  const rows = buildComparisonChartData({
    selectedRange,
    comparisonRange: comparing ? comparisonRange : undefined,
    metrics: agentIds,
    getValuesForDate: (date, period) => {
      const map = period === "selected" ? selectedByKey : compareByKey!;
      const values: Record<string, number> = {};
      for (const agentId of agentIds) {
        values[agentId] = map.get(`${date}:${agentId}`) ?? 0;
      }
      return values;
    },
  });

  const data: ChartRow[] = rows.map((row) => ({
    ...row,
    date: row.name,
  }));

  return { data, agentIds };
}

function ConversationsTooltip({
  active,
  payload,
  label,
  agentNameMap,
  comparing,
}: TooltipProps<number, string> & {
  agentNameMap: Record<string, string>;
  comparing: boolean;
}) {
  if (!active || !payload?.length) return null;

  const row = payload[0]?.payload as ChartRow | undefined;
  const agentKeys = [
    ...new Set(
      payload
        .map((p) => String(p.dataKey ?? ""))
        .filter((k) => k && !isCompareSeriesKey(k)),
    ),
  ];

  return (
    <div className="rounded-lg border border-zinc-200 bg-white px-3 py-2 text-xs shadow-md">
      <p className="mb-1.5 font-medium text-zinc-900">{label}</p>
      {comparing && row && (
        <div className="mb-2 space-y-0.5 text-[10px] text-muted-foreground">
          <p>Selected: {formatChartDayLabel(row.selectedDate)}</p>
          {row.comparisonDate ? (
            <p>Comparison: {formatChartDayLabel(row.comparisonDate)}</p>
          ) : (
            <p>Comparison: —</p>
          )}
        </div>
      )}
      <div className="space-y-1">
        {agentKeys.map((agentId) => {
          const current = payload.find((p) => p.dataKey === agentId)?.value ?? 0;
          const previous = payload.find((p) => p.dataKey === compareSeriesKey(agentId))?.value;
          const name = agentNameMap[agentId] ?? `${agentId.slice(0, 8)}…`;
          return (
            <div key={agentId} className="flex items-center justify-between gap-4">
              <span className="text-muted-foreground">{name}</span>
              <span className="font-medium tabular-nums text-zinc-800">
                {Number(current).toLocaleString()}
                {comparing && previous != null && (
                  <span className="ml-1.5 font-normal text-muted-foreground">
                    / {Number(previous).toLocaleString()}
                  </span>
                )}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function AgentExecutionChart({
  items,
  compareItems,
  dateRange,
  comparisonRange,
  comparedWithLabel,
  loading,
  agentNameMap,
}: AgentExecutionChartProps) {
  const comparing = Boolean(comparisonRange?.from && comparisonRange?.to);
  const comparisonRangeLabel = formatPeriodRangeLabel(comparisonRange);

  const { data, agentIds } = useMemo(
    () =>
      buildChartData(
        items,
        comparing ? compareItems : undefined,
        dateRange,
        comparisonRange,
      ),
    [items, compareItems, dateRange, comparisonRange, comparing],
  );

  const totalConversations = items.reduce((s, i) => s + i.unique_conversations, 0);
  const compareTotal = (compareItems ?? []).reduce((s, i) => s + i.unique_conversations, 0);
  const hasDateRange = Boolean(dateRange?.from && dateRange?.to);

  if (loading) {
    return <AnalyticsChartCardSkeleton variant="area" />;
  }

  const legendFormatter = (key: string) => {
    if (isCompareSeriesKey(key)) {
      const agentId = key.replace(/__compare$/, "");
      const name = agentNameMap[agentId] ?? `${agentId.slice(0, 8)}…`;
      return compareLegendLabel(name, comparisonRangeLabel);
    }
    return agentNameMap[key] ?? `${key.slice(0, 8)}…`;
  };

  return (
    <Card className={cn("bg-white shadow-sm", analyticsFadeUpClass)}>
      <CardHeader className="pb-0">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <CardTitle className="text-sm font-semibold text-zinc-700">Daily Conversations</CardTitle>
          <div className="flex flex-wrap items-center gap-4 text-xs text-muted-foreground">
            <span className="flex items-center gap-1.5">
              <span className="inline-block h-0 w-4 border-t-2 border-emerald-500" aria-hidden />
              Selected
              <span className="ml-0.5 font-semibold text-zinc-700 tabular-nums">
                {totalConversations.toLocaleString()}
              </span>
            </span>
            {comparing && (
              <span className="flex items-center gap-1.5">
                <span
                  className="inline-block h-0 w-4 border-t-2 border-dashed border-emerald-500/70"
                  aria-hidden
                />
                Comparison
                <span className="ml-0.5 font-semibold text-zinc-700 tabular-nums">
                  {compareTotal.toLocaleString()}
                </span>
              </span>
            )}
          </div>
        </div>
        {comparing && (
          <div className="pt-2">
            <PeriodComparisonChartHint comparedWithLabel={comparedWithLabel} />
          </div>
        )}
      </CardHeader>
      <CardContent className="pt-4">
        {!hasDateRange || data.length === 0 ? (
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
              <CartesianGrid strokeDasharray="3 3" stroke="#f4f4f5" vertical={false} />
              <XAxis
                dataKey="date"
                axisLine={false}
                tickLine={false}
                tick={{ fontSize: 11, fill: "#a1a1aa" }}
                dy={6}
                interval="preserveStartEnd"
              />
              <YAxis
                axisLine={false}
                tickLine={false}
                tick={{ fontSize: 11, fill: "#a1a1aa" }}
                allowDecimals={false}
              />
              <Tooltip
                content={
                  <ConversationsTooltip agentNameMap={agentNameMap} comparing={comparing} />
                }
                cursor={{ stroke: "#e4e4e7", strokeWidth: 1 }}
              />
              {(agentIds.length > 1 || comparing) && (
                <Legend formatter={legendFormatter} wrapperStyle={{ fontSize: "11px", paddingTop: "8px" }} />
              )}
              {agentIds.map((agentId, i) => {
                const color = COLORS[i % COLORS.length];
                const showFill = agentIds.length === 1 && !comparing;
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
                    connectNulls
                  />
                );
              })}
              {comparing &&
                agentIds.map((agentId, i) => {
                  const color = COLORS[i % COLORS.length];
                  return (
                    <Area
                      key={compareSeriesKey(agentId)}
                      type="monotone"
                      dataKey={compareSeriesKey(agentId)}
                      stroke={color}
                      strokeWidth={2}
                      strokeDasharray="6 4"
                      strokeOpacity={0.65}
                      dot={false}
                      activeDot={{ r: 4, strokeWidth: 0 }}
                      fill="none"
                      connectNulls
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
