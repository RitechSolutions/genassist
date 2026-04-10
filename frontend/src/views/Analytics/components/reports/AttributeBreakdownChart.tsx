import { useEffect, useMemo, useState } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/card";
import { Skeleton } from "@/components/skeleton";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/select";
import {
  fetchCustomAttributeKeys,
  fetchCustomAttributeBreakdown,
  type CustomAttributeBreakdownItem,
} from "@/services/analyticsReports";
import type { DateRange } from "react-day-picker";
import { format } from "date-fns";

const ROW_HEIGHT = 44;
const CHART_MIN_HEIGHT = 180;
const CHART_PADDING = 40;

const formatScore = (v: number | null): string =>
  v != null ? `${Math.round(v * 10)}%` : "—";

interface AttributeBreakdownChartProps {
  agentId?: string;
  dateRange?: DateRange;
}

export const AttributeBreakdownChart = ({
  agentId,
  dateRange,
}: AttributeBreakdownChartProps) => {
  const [keys, setKeys] = useState<string[]>([]);
  const [selectedKey, setSelectedKey] = useState<string>("");
  const [data, setData] = useState<CustomAttributeBreakdownItem[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const id = agentId !== "all" ? agentId : undefined;
    fetchCustomAttributeKeys(id).then((k) => {
      setKeys(k);
      if (k.length > 0 && !k.includes(selectedKey)) {
        setSelectedKey(k[0]);
      }
    });
  }, [agentId]);

  const fromDateStr = useMemo(
    () => (dateRange?.from ? format(dateRange.from, "yyyy-MM-dd") : undefined),
    [dateRange?.from?.getTime()]
  );
  const toDateStr = useMemo(
    () => (dateRange?.to ? format(dateRange.to, "yyyy-MM-dd") + " 23:59:59" : undefined),
    [dateRange?.to?.getTime()]
  );

  useEffect(() => {
    if (!selectedKey) {
      setData([]);
      return;
    }
    setLoading(true);
    fetchCustomAttributeBreakdown(selectedKey, {
      agent_id: agentId !== "all" ? agentId : undefined,
      from_date: fromDateStr,
      to_date: toDateStr,
    })
      .then(setData)
      .finally(() => setLoading(false));
  }, [selectedKey, agentId, fromDateStr, toDateStr]);

  if (keys.length === 0) return null;

  const totalConversations = data.reduce((sum, d) => sum + d.conversation_count, 0);
  const chartHeight = Math.max(CHART_MIN_HEIGHT, data.length * ROW_HEIGHT + CHART_PADDING);

  return (
    <Card className="mt-6">
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-4">
        <div>
          <CardTitle className="text-base font-semibold">
            Conversations by Attribute
          </CardTitle>
          {!loading && data.length > 0 && (
            <p className="text-xs text-muted-foreground mt-1">
              {totalConversations} conversation{totalConversations !== 1 ? "s" : ""} across {data.length} value{data.length !== 1 ? "s" : ""}
            </p>
          )}
        </div>
        <Select value={selectedKey} onValueChange={setSelectedKey}>
          <SelectTrigger className="w-44">
            <SelectValue placeholder="Select attribute" />
          </SelectTrigger>
          <SelectContent>
            {keys.map((k) => (
              <SelectItem key={k} value={k}>
                {k}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </CardHeader>
      <CardContent>
        {loading ? (
          <div className="space-y-4 py-4">
            {[1, 0.75, 0.5].map((w, i) => (
              <div key={i} className="flex items-center gap-3">
                <Skeleton className="h-4 w-20" />
                <Skeleton className="h-8 rounded" style={{ width: `${w * 100}%` }} />
              </div>
            ))}
          </div>
        ) : data.length === 0 ? (
          <p className="text-sm text-muted-foreground text-center py-12">
            No data for this attribute yet.
          </p>
        ) : (
          <>
            <ResponsiveContainer width="100%" height={chartHeight}>
              <BarChart
                data={data}
                layout="vertical"
                margin={{ top: 4, right: 24, left: 4, bottom: 4 }}
                barCategoryGap="20%"
              >
                <CartesianGrid
                  strokeDasharray="3 3"
                  horizontal={false}
                  stroke="#f0f0f0"
                />
                <XAxis
                  type="number"
                  allowDecimals={false}
                  tick={{ fontSize: 11, fill: "#9ca3af" }}
                  axisLine={{ stroke: "#e5e7eb" }}
                  tickLine={false}
                />
                <YAxis
                  type="category"
                  dataKey="value"
                  width={140}
                  tick={{ fontSize: 12, fill: "#374151", fontWeight: 500 }}
                  axisLine={false}
                  tickLine={false}
                />
                <RechartsTooltip
                  cursor={{ fill: "rgba(0,0,0,0.04)" }}
                  contentStyle={{
                    borderRadius: 8,
                    border: "1px solid #e5e7eb",
                    boxShadow: "0 4px 6px -1px rgba(0,0,0,0.07)",
                    fontSize: 12,
                    padding: "8px 12px",
                  }}
                  formatter={(val: number) => [val, "Conversations"]}
                  labelStyle={{ fontWeight: 600, marginBottom: 2 }}
                />
                <Bar
                  dataKey="conversation_count"
                  fill="#3b82f6"
                  radius={[0, 6, 6, 0]}
                  name="Conversations"
                  maxBarSize={32}
                />
              </BarChart>
            </ResponsiveContainer>

            {/* Metrics table */}
            <div className="mt-6 rounded-lg border border-gray-100 overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-gray-50/80">
                    <th className="text-left py-2.5 px-4 font-medium text-muted-foreground capitalize">
                      {selectedKey}
                    </th>
                    <th className="text-right py-2.5 px-4 font-medium text-muted-foreground">
                      Conversations
                    </th>
                    <th className="text-right py-2.5 px-4 font-medium text-muted-foreground">
                      Satisfaction
                    </th>
                    <th className="text-right py-2.5 px-4 font-medium text-muted-foreground">
                      Resolution
                    </th>
                    <th className="text-right py-2.5 px-4 font-medium text-muted-foreground">
                      Efficiency
                    </th>
                    <th className="text-right py-2.5 px-4 font-medium text-muted-foreground">
                      Quality
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {data.map((row) => {
                    const pct = totalConversations > 0
                      ? Math.round((row.conversation_count / totalConversations) * 100)
                      : 0;
                    return (
                      <tr
                        key={row.value}
                        className="border-t border-gray-100 hover:bg-gray-50/50"
                      >
                        <td className="py-2.5 px-4 font-medium">{row.value}</td>
                        <td className="text-right py-2.5 px-4 tabular-nums">
                          {row.conversation_count}
                          <span className="text-muted-foreground text-xs ml-1">({pct}%)</span>
                        </td>
                        <td className="text-right py-2.5 px-4 tabular-nums">{formatScore(row.avg_satisfaction)}</td>
                        <td className="text-right py-2.5 px-4 tabular-nums">{formatScore(row.avg_resolution_rate)}</td>
                        <td className="text-right py-2.5 px-4 tabular-nums">{formatScore(row.avg_efficiency)}</td>
                        <td className="text-right py-2.5 px-4 tabular-nums">{formatScore(row.avg_quality)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
};
