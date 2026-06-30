import { useEffect, useState, useMemo } from "react";
import { subDays } from "date-fns";
import { toExpandedUTCDateRange } from "@/helpers/analyticsParams";
import { cn } from "@/helpers/utils";
import { DateRange } from "react-day-picker";
import { SidebarProvider, SidebarTrigger } from "@/components/sidebar";
import { AppSidebar } from "@/layout/app-sidebar";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/select";
import { DataTable, type Column } from "@/components/ui/data-table";
import { NodeBreakdownChart } from "../components/reports/NodeBreakdownChart";
import {
  AnalyticsFilters,
  analyticsFilterSelectTriggerClassName,
} from "../components/AnalyticsFilters";
import { AnalyticsPageHeader } from "../components/AnalyticsPageHeader";
import { analyticsFadeUpClass } from "../constants/animations";
import { NodeAnalyticsTableEmptyState } from "../components/AnalyticsEmptyStates";
import { NodeAnalyticsPageSkeleton } from "../components/skeletons";
import { useAnalyticsFilters } from "../hooks/useAnalyticsFilters";
import { usePersistedDateRange } from "@/hooks/usePersistedDateRange";
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
  const [dateRange, setDateRange] = usePersistedDateRange({
    from: subDays(new Date(), 7),
    to: new Date(),
  });
  const [nodeTypeFilter, setNodeTypeFilter] = useState("all");

  const {
    groups,
    showGroupFilter,
    groupFilter,
    setGroupFilter,
    agentFilter,
    setAgentFilter,
    agents,
    agentNameMap,
    filterParams,
  } = useAnalyticsFilters();
  const [nodeTypeOptions, setNodeTypeOptions] = useState<string[]>([]);
  const [items, setItems] = useState<NodeDailyStatsItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = async (
    range: DateRange | undefined,
    nodeType: string,
    filters: { agent_id?: string; group_id?: string },
  ) => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchNodeDailyStats({
        ...toExpandedUTCDateRange(range),
        node_type: nodeType !== "all" ? nodeType : undefined,
        ...filters,
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
    loadData(dateRange, nodeTypeFilter, filterParams);
  }, [dateRange, nodeTypeFilter, filterParams.agent_id, filterParams.group_id]);

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
    ...filterParams,
    node_type: nodeTypeFilter !== "all" ? nodeTypeFilter : undefined,
    ...toExpandedUTCDateRange(dateRange),
  };

  const canExport = !loading && agentBreakdown.length > 0;

  return (
    <SidebarProvider>
      <div className="min-h-screen flex w-full overflow-x-hidden">
        <AppSidebar />
        <main className="flex-1 flex flex-col bg-zinc-100 min-w-0 relative peer-data-[state=expanded]:md:ml-[calc(var(--sidebar-width)-2px)] peer-data-[state=collapsed]:md:ml-0 transition-[margin] duration-200">
          <SidebarTrigger className="fixed top-6 z-10 h-8 w-8 bg-white/50 backdrop-blur-sm hover:bg-white/70 rounded-full shadow-md transition-[left] duration-200" />
          <div className="flex-1 p-4 sm:p-6 lg:p-8">
            <div className="max-w-7xl mx-auto space-y-6">

              <AnalyticsPageHeader
                title="Node Analytics"
                subtitle="Workflow node execution metrics by type and date"
              >
                <AnalyticsFilters
                  groups={showGroupFilter ? groups : undefined}
                  groupFilter={groupFilter}
                  onGroupFilterChange={setGroupFilter}
                  agents={agents}
                  agentFilter={agentFilter}
                  onAgentFilterChange={setAgentFilter}
                  dateRange={dateRange}
                  onDateRangeChange={setDateRange}
                >
                  <Select value={nodeTypeFilter} onValueChange={setNodeTypeFilter}>
                    <SelectTrigger className={cn(analyticsFilterSelectTriggerClassName, "shrink-0")}>
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
                    disabled={!canExport}
                  />
                </AnalyticsFilters>
              </AnalyticsPageHeader>

              {loading ? (
                <NodeAnalyticsPageSkeleton />
              ) : (
                <div className="space-y-6 sm:space-y-8">
              <NodeBreakdownChart items={items} loading={false} />

              <div className={analyticsFadeUpClass}>
                <DataTable
                  data={agentBreakdown}
                  columns={agentBreakdownColumns}
                  loading={false}
                  error={error}
                  emptyState={<NodeAnalyticsTableEmptyState />}
                  keyExtractor={(item) => item.id}
                  pageSize={10}
                />
              </div>
                </div>
              )}

            </div>
          </div>
        </main>
      </div>
    </SidebarProvider>
  );
};

export default NodeAnalyticsPage;
