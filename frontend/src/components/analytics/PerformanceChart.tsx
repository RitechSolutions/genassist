import { useState, useEffect, useRef } from "react";
import { Card } from "@/components/card";
import { Area, AreaChart, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend } from "recharts";
import { fetchMetricsDaily, type DailyMetricsItem } from "@/services/metrics";
import { toMetricsApiParams } from "@/helpers/analyticsParams";
import type { DateRange } from "react-day-picker";

type ChartRow = {
  name: string;
  satisfaction: number;
  serviceQuality: number;
  resolutionRate: number;
};

interface PerformanceChartProps {
  dateRange?: DateRange;
  agentId?: string;
}

const LABELS: Record<string, string> = {
  satisfaction: "Customer Satisfaction",
  serviceQuality: "Quality of Service",
  resolutionRate: "Resolution Rate",
};

function formatDateLabel(dateStr: string): string {
  const d = new Date(dateStr + "T00:00:00");
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

function toChartRows(items: DailyMetricsItem[]): ChartRow[] {
  return items.map((item) => ({
    name: formatDateLabel(item.date),
    satisfaction: item.satisfaction,
    serviceQuality: item.quality_of_service,
    resolutionRate: item.resolution_rate,
  }));
}

export const PerformanceChart = ({ dateRange, agentId }: PerformanceChartProps) => {
  const [data, setData] = useState<ChartRow[]>([]);
  const [loading, setLoading] = useState(true);
  const fetchIdRef = useRef(0);

  useEffect(() => {
    const fetchId = ++fetchIdRef.current;
    const params = toMetricsApiParams(dateRange, agentId);

    const load = async () => {
      setLoading(true);
      try {
        const items = await fetchMetricsDaily(params);
        if (fetchId !== fetchIdRef.current) return;
        setData(toChartRows(items));
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
  }, [dateRange?.from?.getTime(), dateRange?.to?.getTime(), agentId]);

  return (
    <Card className="p-4 sm:p-6 shadow-sm animate-fade-up bg-white">
      <h2 className="text-base sm:text-lg font-semibold mb-4">Daily Performance Trend</h2>
      <div className={`h-[300px] sm:h-[400px] w-full transition-opacity duration-200 ${loading ? "opacity-60" : ""}`}>
        {data.length === 0 && !loading ? (
          <div className="flex items-center justify-center h-full text-sm text-muted-foreground">
            No data available for the selected period.
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data}>
              <defs>
                <linearGradient id="colorSatisfaction" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#16a34a" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#16a34a" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="colorServiceQuality" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#9333ea" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#9333ea" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="colorResolutionRate" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#dc2626" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#dc2626" stopOpacity={0} />
                </linearGradient>
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
              <Tooltip
                contentStyle={{
                  backgroundColor: "#fff",
                  border: "none",
                  borderRadius: "8px",
                  boxShadow: "0 2px 8px rgba(0,0,0,0.1)",
                  fontSize: "12px",
                }}
                formatter={(value: number, name: string) => [`${value}%`, LABELS[name] ?? name]}
              />
              <Legend
                formatter={(value: string) => LABELS[value] ?? value}
                wrapperStyle={{ fontSize: "12px", paddingTop: "8px" }}
              />

              <Area type="monotone" dataKey="satisfaction" stroke="#16a34a" strokeWidth={2} fill="url(#colorSatisfaction)" name="satisfaction" />
              <Area type="monotone" dataKey="serviceQuality" stroke="#9333ea" strokeWidth={2} fill="url(#colorServiceQuality)" name="serviceQuality" />
              <Area type="monotone" dataKey="resolutionRate" stroke="#dc2626" strokeWidth={2} fill="url(#colorResolutionRate)" name="resolutionRate" />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>
    </Card>
  );
};
