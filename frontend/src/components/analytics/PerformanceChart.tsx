import { useState, useEffect, useRef, useMemo } from "react";
import { Card } from "@/components/card";
import { cn } from "@/helpers/utils";
import { AnalyticsChartCardSkeleton } from "@/components/skeletons";
import { PerformanceTrendChartEmptyState } from "@/views/Analytics/components/AnalyticsEmptyStates";
import { PeriodComparisonChartHint } from "@/views/Analytics/components/reports/PeriodComparisonChartHint";
import { analyticsFadeUpClass } from "@/views/Analytics/constants/animations";
import {
  Area,
  AreaChart,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Legend,
  type TooltipProps,
} from "recharts";
import { fetchMetricsDaily, type DailyMetricsItem } from "@/services/metrics";
import { toMetricsApiParams } from "@/helpers/analyticsParams";
import {
  buildComparisonChartData,
  type ComparisonChartRow,
} from "@/helpers/analyticsPeriodComparison";
import {
  compareLegendLabel,
  compareSeriesKey,
  formatChartDayLabel,
  formatPeriodRangeLabel,
  isCompareSeriesKey,
  normalizeDateKey,
} from "@/helpers/alignChartPeriods";
import type { DateRange } from "react-day-picker";

const METRIC_KEYS = ["satisfaction", "serviceQuality", "resolutionRate", "efficiency"] as const;
type MetricKey = (typeof METRIC_KEYS)[number];

interface PerformanceChartProps {
  dateRange?: DateRange;
  agentId?: string;
  groupId?: string;
  comparisonRange?: DateRange;
  comparedWithLabel?: string | null;
}

const LABELS: Record<MetricKey, string> = {
  satisfaction: "Customer Satisfaction",
  serviceQuality: "Quality of Service",
  resolutionRate: "Resolution Rate",
  efficiency: "Efficiency",
};

const SERIES: { key: MetricKey; color: string; field: keyof DailyMetricsItem }[] = [
  { key: "satisfaction", color: "#10b981", field: "satisfaction" },
  { key: "serviceQuality", color: "#8b5cf6", field: "quality_of_service" },
  { key: "resolutionRate", color: "#f59e0b", field: "resolution_rate" },
  { key: "efficiency", color: "#06b6d4", field: "efficiency" },
];

function indexMetricsByDate(items: DailyMetricsItem[]): Map<string, DailyMetricsItem> {
  const map = new Map<string, DailyMetricsItem>();
  for (const item of items) {
    map.set(normalizeDateKey(item.date), item);
  }
  return map;
}

function metricValue(item: DailyMetricsItem | undefined, field: keyof DailyMetricsItem): number {
  if (!item) return 0;
  const v = item[field];
  return typeof v === "number" && !Number.isNaN(v) ? v : 0;
}

function buildChartRows(
  selectedRange: DateRange | undefined,
  currentItems: DailyMetricsItem[],
  compareItems: DailyMetricsItem[],
  comparisonRange: DateRange | undefined,
): ComparisonChartRow[] {
  if (!selectedRange?.from || !selectedRange?.to) return [];

  const currentByDate = indexMetricsByDate(currentItems);
  const compareByDate = indexMetricsByDate(compareItems);

  const getValuesForDate = (date: string, period: "selected" | "comparison"): Record<MetricKey, number> => {
    const map = period === "selected" ? currentByDate : compareByDate;
    const item = map.get(date);
    const values = {} as Record<MetricKey, number>;
    for (const { key, field } of SERIES) {
      values[key] = metricValue(item, field);
    }
    return values;
  };

  return buildComparisonChartData({
    selectedRange,
    comparisonRange,
    metrics: METRIC_KEYS,
    getValuesForDate,
  });
}

function PerformanceTooltip({
  active,
  payload,
  label,
  comparing,
}: TooltipProps<number, string> & { comparing: boolean }) {
  if (!active || !payload?.length) return null;

  const row = payload[0]?.payload as ComparisonChartRow | undefined;

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
        {METRIC_KEYS.map((key) => {
          const currentEntry = payload.find((p) => p.dataKey === key);
          const compareEntry = payload.find((p) => p.dataKey === compareSeriesKey(key));
          const currentVal = currentEntry?.value ?? 0;
          const compareVal = compareEntry?.value;

          return (
            <div key={key} className="flex items-center justify-between gap-4">
              <span className="text-muted-foreground">{LABELS[key]}</span>
              <span className="font-medium tabular-nums text-zinc-800">
                {`${currentVal}%`}
                {comparing && compareVal != null && (
                  <span className="ml-1.5 font-normal text-muted-foreground">/ {compareVal}%</span>
                )}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export const PerformanceChart = ({
  dateRange,
  agentId,
  groupId,
  comparisonRange,
  comparedWithLabel,
}: PerformanceChartProps) => {
  const [data, setData] = useState<ComparisonChartRow[]>([]);
  const [loading, setLoading] = useState(true);
  const fetchIdRef = useRef(0);
  const comparing = Boolean(comparisonRange?.from && comparisonRange?.to);
  const comparisonRangeLabel = formatPeriodRangeLabel(comparisonRange);

  useEffect(() => {
    const fetchId = ++fetchIdRef.current;
    const params = toMetricsApiParams(dateRange, agentId, groupId);
    const compareParams = comparing
      ? toMetricsApiParams(comparisonRange, agentId, groupId)
      : undefined;

    const load = async () => {
      setLoading(true);
      try {
        const [currentItems, compareItems] = await Promise.all([
          fetchMetricsDaily(params),
          compareParams ? fetchMetricsDaily(compareParams) : Promise.resolve([]),
        ]);
        if (fetchId !== fetchIdRef.current) return;
        setData(
          buildChartRows(dateRange, currentItems, compareItems, comparisonRange),
        );
      } catch {
        if (fetchId === fetchIdRef.current) {
          setData([]);
        }
      } finally {
        if (fetchId === fetchIdRef.current) {
          setLoading(false);
        }
      }
    };

    load();
  }, [
    dateRange?.from?.getTime(),
    dateRange?.to?.getTime(),
    agentId,
    groupId,
    comparisonRange?.from?.getTime(),
    comparisonRange?.to?.getTime(),
    comparing,
  ]);

  const legendFormatter = useMemo(
    () => (value: string) => {
      if (isCompareSeriesKey(value)) {
        const base = value.replace(/__compare$/, "") as MetricKey;
        return compareLegendLabel(LABELS[base] ?? base, comparisonRangeLabel);
      }
      return LABELS[value as MetricKey] ?? value;
    },
    [comparisonRangeLabel],
  );

  const hasDateRange = Boolean(dateRange?.from && dateRange?.to);

  if (loading && data.length === 0) {
    return <AnalyticsChartCardSkeleton variant="area" />;
  }

  return (
    <Card className={cn("bg-white p-4 shadow-sm sm:p-6", analyticsFadeUpClass)}>
      <h2 className="text-base font-semibold sm:text-lg">Daily Performance Trend</h2>
      {comparing && (
        <PeriodComparisonChartHint comparedWithLabel={comparedWithLabel} />
      )}
      <div
        className={cn(
          "h-[300px] w-full transition-opacity duration-200 sm:h-[400px]",
          comparing && !loading ? "mt-1" : "mt-4",
          loading && "opacity-60",
        )}
      >
        {!hasDateRange || (data.length === 0 && !loading) ? (
          <div className="flex h-full min-h-[240px] items-center justify-center sm:min-h-[300px]">
            <PerformanceTrendChartEmptyState />
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data}>
              <defs>
                {SERIES.map(({ key, color }) => (
                  <linearGradient key={key} id={`color-${key}`} x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor={color} stopOpacity={0.15} />
                    <stop offset="95%" stopColor={color} stopOpacity={0} />
                  </linearGradient>
                ))}
              </defs>

              <XAxis
                dataKey="name"
                axisLine={false}
                tickLine={false}
                tick={{ fill: "#666", fontSize: 10, dy: 10 }}
                interval="preserveStartEnd"
              />
              <YAxis
                domain={[0, 100]}
                axisLine={false}
                tickLine={false}
                tick={{ fill: "#666", fontSize: 10 }}
                width={35}
                tickFormatter={(value) => `${value}%`}
              />
              <Tooltip content={<PerformanceTooltip comparing={comparing} />} />
              <Legend
                formatter={legendFormatter}
                wrapperStyle={{ fontSize: "11px", paddingTop: "8px" }}
              />

              {SERIES.map(({ key, color }) => (
                <Area
                  key={key}
                  type="monotone"
                  dataKey={key}
                  stroke={color}
                  strokeWidth={2}
                  fill={`url(#color-${key})`}
                  name={key}
                  connectNulls
                />
              ))}

              {comparing &&
                SERIES.map(({ key, color }) => (
                  <Area
                    key={compareSeriesKey(key)}
                    type="monotone"
                    dataKey={compareSeriesKey(key)}
                    stroke={color}
                    strokeWidth={2}
                    strokeDasharray="6 4"
                    strokeOpacity={0.65}
                    fill="none"
                    name={compareSeriesKey(key)}
                    connectNulls
                  />
                ))}
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>
    </Card>
  );
};
