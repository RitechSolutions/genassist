import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/card";
import { Skeleton } from "@/components/skeleton";
import type { NodeDailyStatsItem } from "@/interfaces/analyticsReports.interface";
import { nodeTypeLabel } from "@/helpers/nodeTypeLabel";

const TOP_N = 12;
const ROW_HEIGHT = 36;
const CHART_OVERHEAD = 32;

interface NodeBreakdownChartProps {
  items: NodeDailyStatsItem[];
  loading: boolean;
}

interface AggregatedNode {
  label: string;
  executions: number;
  success: number;
  failures: number;
  successRate: number;
}

function aggregateByNodeType(items: NodeDailyStatsItem[]): AggregatedNode[] {
  const map = new Map<string, { executions: number; success: number; failures: number }>();
  for (const item of items) {
    const existing = map.get(item.node_type);
    if (existing) {
      existing.executions += item.execution_count;
      existing.success += item.success_count;
      existing.failures += item.failure_count;
    } else {
      map.set(item.node_type, {
        executions: item.execution_count,
        success: item.success_count,
        failures: item.failure_count,
      });
    }
  }
  return Array.from(map.entries())
    .map(([type, v]) => ({
      label: nodeTypeLabel(type),
      executions: v.executions,
      success: v.success,
      failures: v.failures,
      successRate: v.executions > 0 ? (v.success / v.executions) * 100 : 0,
    }))
    .sort((a, b) => b.executions - a.executions);
}

const CustomTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null;
  const d = payload[0]?.payload as AggregatedNode;
  return (
    <div className="bg-white border border-border rounded-xl shadow-md p-3 text-xs min-w-[160px]">
      <p className="font-semibold text-zinc-800 mb-2">{label}</p>
      <div className="space-y-1">
        <div className="flex justify-between gap-4">
          <span className="text-muted-foreground">Executions</span>
          <span className="font-medium tabular-nums">{d.executions.toLocaleString()}</span>
        </div>
        <div className="flex justify-between gap-4">
          <span className="text-emerald-600">Success</span>
          <span className="font-medium tabular-nums text-emerald-600">{d.success.toLocaleString()}</span>
        </div>
        <div className="flex justify-between gap-4">
          <span className="text-red-400">Failures</span>
          <span className="font-medium tabular-nums text-red-400">{d.failures.toLocaleString()}</span>
        </div>
        <div className="flex justify-between gap-4 pt-1 border-t border-border mt-1">
          <span className="text-muted-foreground">Success rate</span>
          <span className="font-semibold tabular-nums">{d.successRate.toFixed(1)}%</span>
        </div>
      </div>
    </div>
  );
};

export function NodeBreakdownChart({ items, loading }: NodeBreakdownChartProps) {
  if (loading) {
    return <Skeleton className="h-[320px] rounded-xl w-full" />;
  }

  const all = aggregateByNodeType(items);
  const data = all.slice(0, TOP_N);
  const truncated = all.length > TOP_N;
  const totalExecutions = all.reduce((s, d) => s + d.executions, 0);

  const chartHeight = Math.max(data.length * ROW_HEIGHT + CHART_OVERHEAD, 120);

  return (
    <Card className="bg-white shadow-sm">
      <CardHeader className="pb-0">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <CardTitle className="text-sm font-semibold text-zinc-700">
            Node Type Breakdown
          </CardTitle>
          <div className="flex items-center gap-4 text-xs text-muted-foreground">
            <span className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-blue-400 inline-block" />
              Total
              <span className="font-semibold text-zinc-700 ml-0.5">{totalExecutions.toLocaleString()}</span>
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 inline-block" />
              Success
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-red-400 inline-block" />
              Failures
            </span>
            {truncated && (
              <span className="text-zinc-400">top {TOP_N} of {all.length}</span>
            )}
          </div>
        </div>
      </CardHeader>
      <CardContent className="pt-4">
        {data.length === 0 ? (
          <div className="flex items-center justify-center h-40 text-sm text-muted-foreground">
            No node data available for the selected period.
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={chartHeight}>
            <BarChart
              data={data}
              layout="vertical"
              margin={{ top: 0, right: 16, bottom: 0, left: 8 }}
              barCategoryGap="35%"
              barGap={2}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="#f4f4f5" horizontal={false} />
              <XAxis
                type="number"
                axisLine={false}
                tickLine={false}
                tick={{ fontSize: 11, fill: "#a1a1aa" }}
                allowDecimals={false}
              />
              <YAxis
                type="category"
                dataKey="label"
                width={148}
                axisLine={false}
                tickLine={false}
                tick={{ fontSize: 11, fill: "#52525b" }}
              />
              <Tooltip content={<CustomTooltip />} cursor={{ fill: "#f4f4f5" }} />
              <Bar dataKey="executions" radius={[0, 3, 3, 0]} barSize={8}>
                {data.map((_, i) => (
                  <Cell key={i} fill="#93c5fd" />
                ))}
              </Bar>
              <Bar dataKey="success" radius={[0, 3, 3, 0]} barSize={8}>
                {data.map((_, i) => (
                  <Cell key={i} fill="#10b981" />
                ))}
              </Bar>
              <Bar dataKey="failures" radius={[0, 3, 3, 0]} barSize={8}>
                {data.map((d, i) => (
                  <Cell key={i} fill={d.failures > 0 ? "#f87171" : "#f4f4f5"} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        )}
      </CardContent>
    </Card>
  );
}
