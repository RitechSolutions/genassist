import { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend } from "recharts";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/dialog";
import { fetchAgentNodeBreakdown } from "@/services/analyticsReports";
import type { NodeTypeBreakdownItem } from "@/interfaces/analyticsReports.interface";
import { nodeTypeLabel } from "@/helpers/nodeTypeLabel";

const PALETTE = [
  "#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6",
  "#06b6d4", "#f97316", "#84cc16", "#ec4899", "#14b8a6",
  "#6366f1", "#a78bfa", "#34d399", "#fbbf24", "#fb7185",
];

const TOP_N = 9;

interface AgentNodeBreakdownDialogProps {
  open: boolean;
  onClose: () => void;
  agentId: string;
  agentName: string;
  totalExecutions: number;
  fromDate?: string;
  toDate?: string;
}

export function AgentNodeBreakdownDialog({
  open,
  onClose,
  agentId,
  agentName,
  totalExecutions,
  fromDate,
  toDate,
}: AgentNodeBreakdownDialogProps) {
  const [items, setItems] = useState<NodeTypeBreakdownItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setLoading(true);
    setError(null);
    fetchAgentNodeBreakdown(agentId, { from_date: fromDate, to_date: toDate })
      .then((data) => setItems(data?.items ?? []))
      .catch(() => setError("Failed to load node breakdown."))
      .finally(() => setLoading(false));
  }, [open, agentId, fromDate, toDate]);

  const totalNodeExecutions = items.reduce((s, i) => s + i.execution_count, 0);

  // Build pie data — top N + "Others"
  const sorted = [...items].sort((a, b) => b.execution_count - a.execution_count);
  const topItems = sorted.slice(0, TOP_N);
  const othersCount = sorted.slice(TOP_N).reduce((s, i) => s + i.execution_count, 0);
  const pieData = [
    ...topItems.map((i) => ({ name: nodeTypeLabel(i.node_type), value: i.execution_count })),
    ...(othersCount > 0 ? [{ name: "Others", value: othersCount }] : []),
  ];

  const colorOf = (index: number) => PALETTE[index % PALETTE.length];

  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v) onClose(); }}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>{agentName}</DialogTitle>
          <DialogDescription>
            Node execution breakdown · {totalExecutions.toLocaleString()} total agent{" "}
            {totalExecutions === 1 ? "execution" : "executions"}
          </DialogDescription>
        </DialogHeader>

        {loading && (
          <div className="flex justify-center py-12">
            <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
          </div>
        )}

        {error && (
          <p className="text-sm text-red-500 text-center py-6">{error}</p>
        )}

        {!loading && !error && items.length === 0 && (
          <p className="text-sm text-muted-foreground text-center py-6">
            No node data found for this agent.
          </p>
        )}

        {!loading && !error && items.length > 0 && (
          <div className="space-y-5 mt-1">
            {/* Donut pie chart — execution share */}
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={pieData}
                    dataKey="value"
                    nameKey="name"
                    cx="50%"
                    cy="50%"
                    innerRadius={65}
                    outerRadius={105}
                    paddingAngle={2}
                    strokeWidth={0}
                  >
                    {pieData.map((_, i) => (
                      <Cell key={i} fill={colorOf(i)} />
                    ))}
                  </Pie>
                  <Tooltip
                    formatter={(value: number, name: string) => {
                      const pct = totalNodeExecutions > 0
                        ? ((value / totalNodeExecutions) * 100).toFixed(1)
                        : "0";
                      return [`${value.toLocaleString()} (${pct}%)`, name];
                    }}
                    contentStyle={{
                      fontSize: 12,
                      borderRadius: 8,
                      border: "1px solid #e4e4e7",
                    }}
                  />
                  <Legend
                    iconType="circle"
                    iconSize={8}
                    formatter={(value) =>
                      value.length > 20 ? value.slice(0, 20) + "…" : value
                    }
                    wrapperStyle={{ fontSize: 11 }}
                  />
                </PieChart>
              </ResponsiveContainer>
            </div>

            {/* Per-node detail list */}
            <div className="border rounded-lg overflow-hidden">
              <table className="w-full text-xs">
                <thead>
                  <tr className="bg-zinc-50 border-b">
                    <th className="text-left px-3 py-2 font-medium text-zinc-500">Node Type</th>
                    <th className="text-right px-3 py-2 font-medium text-zinc-500">Executions</th>
                    <th className="text-right px-3 py-2 font-medium text-zinc-500">Success</th>
                    <th className="text-right px-3 py-2 font-medium text-zinc-500">Failed</th>
                    <th className="text-right px-3 py-2 font-medium text-zinc-500">Success %</th>
                    <th className="text-right px-3 py-2 font-medium text-zinc-500">Avg (ms)</th>
                  </tr>
                </thead>
                <tbody>
                  {sorted.map((item, i) => {
                    const successRate =
                      item.success_rate != null
                        ? `${(item.success_rate * 100).toFixed(1)}%`
                        : "—";
                    const pct =
                      totalNodeExecutions > 0
                        ? Math.round((item.execution_count / totalNodeExecutions) * 100)
                        : 0;
                    return (
                      <tr key={item.node_type} className="border-b last:border-0 hover:bg-zinc-50">
                        <td className="px-3 py-2">
                          <div className="flex items-center gap-1.5">
                            <span
                              className="w-2 h-2 rounded-full shrink-0"
                              style={{ backgroundColor: colorOf(i) }}
                            />
                            <span className="text-zinc-700 truncate max-w-[160px]">
                              {nodeTypeLabel(item.node_type)}
                            </span>
                          </div>
                        </td>
                        <td className="px-3 py-2 text-right tabular-nums">
                          {item.execution_count.toLocaleString()}
                          <span className="text-zinc-400 ml-1">({pct}%)</span>
                        </td>
                        <td className="px-3 py-2 text-right tabular-nums text-green-600 font-medium">
                          {item.success_count.toLocaleString()}
                        </td>
                        <td className={`px-3 py-2 text-right tabular-nums font-medium ${item.failure_count > 0 ? "text-red-500" : "text-zinc-400"}`}>
                          {item.failure_count.toLocaleString()}
                        </td>
                        <td className="px-3 py-2 text-right tabular-nums">{successRate}</td>
                        <td className="px-3 py-2 text-right tabular-nums text-zinc-500">
                          {item.avg_execution_ms != null
                            ? `${Math.round(item.avg_execution_ms)}`
                            : "—"}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
