import { useEffect, useState, useMemo } from "react";
import { format, subDays } from "date-fns";
import { DateRange } from "react-day-picker";
import { SidebarProvider, SidebarTrigger } from "@/components/sidebar";
import { AppSidebar } from "@/layout/app-sidebar";
import { useIsMobile } from "@/hooks/useMobile";
import { Card, CardContent } from "@/components/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/select";
import { Info } from "lucide-react";
import { DataTable, type Column } from "@/components/ui/data-table";
import { NodeBreakdownChart } from "../components/reports/NodeBreakdownChart";
import { AnalyticsFilters } from "../components/AnalyticsFilters";
import { useAgentsList } from "../hooks/useAgentsList";
import { fetchNodeDailyStats } from "@/services/analyticsReports";
import type { NodeDailyStatsItem } from "@/interfaces/analyticsReports.interface";
import { nodeTypeLabel } from "@/helpers/nodeTypeLabel";
import { ExportButton } from "@/components/ui/ExportButton";


interface AgentNodeBreakdown {
  id: string;
  agent_id: string;
  node_type: string;
  execution_count: number;
  success_count: number;
  failure_count: number;
  avg_execution_ms: number | null;
}

const NodeAnalyticsPage = () => {
  const isMobile = useIsMobile();

  const [dateRange, setDateRange] = useState<DateRange | undefined>({
    from: subDays(new Date(), 7),
    to: new Date(),
  });
  const [agentFilter, setAgentFilter] = useState("all");
  const [nodeTypeFilter, setNodeTypeFilter] = useState("all");

  const { agents, agentNameMap } = useAgentsList();
  const [nodeTypeOptions, setNodeTypeOptions] = useState<string[]>([]);
  const [items, setItems] = useState<NodeDailyStatsItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = async (
    range: DateRange | undefined,
    nodeType: string,
    agentId: string
  ) => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchNodeDailyStats({
        from_date: range?.from ? format(range.from, "yyyy-MM-dd") : undefined,
        to_date: range?.to ? format(range.to, "yyyy-MM-dd") : undefined,
        node_type: nodeType !== "all" ? nodeType : undefined,
        agent_id: agentId !== "all" ? agentId : undefined,
      });
      const fetched = data?.items ?? [];
      setItems(fetched);
      // Update node type options only when not filtering by node type
      if (nodeType === "all") {
        const types = [...new Set(fetched.map((i) => i.node_type))].sort();
        setNodeTypeOptions(types);
      }
    } catch {
      setError("Failed to load node analytics data.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData(dateRange, nodeTypeFilter, agentFilter);
  }, [dateRange, nodeTypeFilter, agentFilter]);

  const agentBreakdown = useMemo<AgentNodeBreakdown[]>(() => {
    // Use a separate accumulator type to track weighted-average state
    interface Acc extends AgentNodeBreakdown { _total_ms: number; _ms_count: number; }
    const map = new Map<string, Acc>();
    for (const item of items) {
      const id = `${item.agent_id}__${item.node_type}`;
      const acc = map.get(id);
      if (acc) {
        acc.execution_count += item.execution_count;
        acc.success_count += item.success_count;
        acc.failure_count += item.failure_count;
        if (item.avg_execution_ms != null) {
          acc._total_ms += item.avg_execution_ms * item.execution_count;
          acc._ms_count += item.execution_count;
        }
      } else {
        map.set(id, {
          id,
          agent_id: item.agent_id,
          node_type: item.node_type,
          execution_count: item.execution_count,
          success_count: item.success_count,
          failure_count: item.failure_count,
          avg_execution_ms: item.avg_execution_ms,
          _total_ms: item.avg_execution_ms != null ? item.avg_execution_ms * item.execution_count : 0,
          _ms_count: item.avg_execution_ms != null ? item.execution_count : 0,
        });
      }
    }
    return [...map.values()]
      .map(({ _total_ms, _ms_count, ...row }) => ({
        ...row,
        avg_execution_ms: _ms_count > 0 ? _total_ms / _ms_count : null,
      }))
      .sort((a, b) => b.execution_count - a.execution_count);
  }, [items]);

  const agentBreakdownColumns: Column<AgentNodeBreakdown>[] = useMemo(
    () => [
      {
        header: "Agent",
        key: "agent_id",
        cell: (item) => (
          <span className="text-xs text-zinc-600">
            {agentNameMap[item.agent_id] ?? item.agent_id.slice(0, 8) + "…"}
          </span>
        ),
      },
      {
        header: "Node Type",
        key: "node_type",
        description: "The type of workflow node (e.g. LLM, condition, API call).",
        cell: (item) => nodeTypeLabel(item.node_type),
      },
      {
        header: "Executions",
        key: "execution_count",
        description: "Total times this node type was run across all workflows.",
        cell: (item) => item.execution_count.toLocaleString(),
      },
      {
        header: "Success",
        key: "success_count",
        description: "Node runs that completed without errors.",
        cell: (item) => (
          <span className="text-green-600 font-medium">
            {item.success_count.toLocaleString()}
          </span>
        ),
      },
      {
        header: "Failures",
        key: "failure_count",
        description: "Node runs that threw an error or timed out.",
        cell: (item) => (
          <span className={item.failure_count > 0 ? "text-red-500 font-medium" : "text-zinc-400"}>
            {item.failure_count.toLocaleString()}
          </span>
        ),
      },
      {
        header: "Avg Exec (ms)",
        key: "avg_execution_ms",
        description: "Average time this node type takes to complete, in milliseconds.",
        cell: (item) =>
          item.avg_execution_ms != null ? `${Math.round(item.avg_execution_ms)} ms` : "—",
      },
    ],
    [agentNameMap]
  );

  const exportParams = {
    agent_id: agentFilter !== "all" ? agentFilter : undefined,
    node_type: nodeTypeFilter !== "all" ? nodeTypeFilter : undefined,
    from_date: dateRange?.from ? format(dateRange.from, "yyyy-MM-dd") : undefined,
    to_date: dateRange?.to ? format(dateRange.to, "yyyy-MM-dd") : undefined,
  };

  return (
    <SidebarProvider>
      <div className="min-h-screen flex w-full overflow-x-hidden">
        {!isMobile && <AppSidebar />}
        <main className="flex-1 flex flex-col bg-zinc-100 min-w-0 relative peer-data-[state=expanded]:md:ml-[calc(var(--sidebar-width)-2px)] peer-data-[state=collapsed]:md:ml-0 transition-[margin] duration-200">
          <SidebarTrigger className="fixed top-4 z-10 h-8 w-8 bg-white/50 backdrop-blur-sm hover:bg-white/70 rounded-full shadow-md transition-[left] duration-200" />
          <div className="flex-1 p-4 sm:p-6 lg:p-8">
            <div className="max-w-7xl mx-auto space-y-6">

              {/* Header */}
              <header className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                <div>
                  <h1 className="text-2xl sm:text-3xl font-bold mb-1 animate-fade-down">
                    Node Analytics
                  </h1>
                  <p className="text-sm text-muted-foreground animate-fade-up">
                    Workflow node execution metrics by type and date
                  </p>
                </div>

                {/* Filters */}
                <AnalyticsFilters
                  agents={agents}
                  agentFilter={agentFilter}
                  onAgentFilterChange={setAgentFilter}
                  dateRange={dateRange}
                  onDateRangeChange={setDateRange}
                >
                  {/* Node type filter */}
                  <Select value={nodeTypeFilter} onValueChange={setNodeTypeFilter}>
                    <SelectTrigger className="w-44">
                      <SelectValue placeholder="All node types" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All node types</SelectItem>
                      {nodeTypeOptions.map((t) => (
                        <SelectItem key={t} value={t}>
                          {nodeTypeLabel(t)}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>

                  <ExportButton
                    endpoint="/analytics/nodes/export"
                    params={exportParams}
                    filename="node-analytics"
                    disabled={loading || agentBreakdown.length === 0}
                  />
                </AnalyticsFilters>
              </header>

              {/* Empty-data notice */}
              {!loading && items.length === 0 && !error && (
                <Card className="bg-blue-50 border-blue-200">
                  <CardContent className="p-4 flex items-center gap-3">
                    <Info className="w-5 h-5 text-blue-500 flex-shrink-0" />
                    <p className="text-sm text-blue-700">
                      No node data yet. Run the aggregation task to populate the summary tables.
                    </p>
                  </CardContent>
                </Card>
              )}

              {/* Node breakdown bar chart */}
              <NodeBreakdownChart items={items} loading={loading} />

              {/* Agent breakdown table */}
              <div>
                <DataTable
                  data={agentBreakdown}
                  columns={agentBreakdownColumns}
                  loading={loading}
                  error={error}
                  emptyMessage="No node data for the selected period."
                  keyExtractor={(item) => item.id}
                  pageSize={10}
                />
              </div>

            </div>
          </div>
        </main>
      </div>
    </SidebarProvider>
  );
};

export default NodeAnalyticsPage;
