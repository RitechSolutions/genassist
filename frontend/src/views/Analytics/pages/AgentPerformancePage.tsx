import { useCallback, useEffect, useState, useMemo } from "react";
import { subDays } from "date-fns";
import { toExpandedUTCDateRange } from "@/helpers/analyticsParams";
import { Settings2, TrendingDown, ShieldCheck, ThumbsUp, ThumbsDown } from "lucide-react";
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
import { SummaryStatsCards } from "../components/reports/SummaryStatsCards";
import { AgentExecutionChart } from "../components/reports/AgentExecutionChart";
import { AgentNodeBreakdownDialog } from "../components/reports/AgentNodeBreakdownDialog";
import { AnalyticsFilters } from "../components/AnalyticsFilters";
import { AnalyticsPageHeader } from "../components/AnalyticsPageHeader";
import { analyticsFadeUpClass } from "../constants/animations";
import {
  AgentPerformanceTableEmptyState,
  AnalyticsAggregatedDataEmptyState,
} from "../components/AnalyticsEmptyStates";
import { AgentPerformancePageSkeleton } from "../components/skeletons";
import { cn } from "@/helpers/utils";
import { useAnalyticsFilters } from "../hooks/useAnalyticsFilters";
import {
  fetchAgentStatsSummary,
  fetchAgentDailyStats,
  fetchAgentNodeBreakdown,
} from "@/services/analyticsReports";
import type {
  AgentStatsSummaryResponse,
  AgentDailyStatsItem,
  NodeTypeBreakdownItem,
} from "@/interfaces/analyticsReports.interface";
import { nodeTypeLabel } from "@/helpers/nodeTypeLabel";
import { ExportButton } from "@/components/ui/ExportButton";
import { useAnalyticsPeriodComparison } from "../hooks/useAnalyticsPeriodComparison";
import type { PeriodPreset } from "@/helpers/analyticsPeriodComparison";

const LS_KEY = (agentId: string) => `analytics_escalation_node_${agentId}`;

function getResponseTimeColor(ms: number): string {
  if (ms < 3000) return "text-emerald-600";
  if (ms < 10000) return "text-amber-600";
  return "text-rose-600";
}

function formatResponseTime(ms: number | null): string {
  if (ms == null) return "—";
  return ms < 1000 ? `${Math.round(ms)} ms` : `${(ms / 1000).toFixed(1)}s`;
}

interface AgentAggregated {
  id: string;
  agent_id: string;
  unique_conversations: number;
  finalized_conversations: number;
  in_progress_conversations: number;
  execution_count: number;
  success_count: number;
  error_count: number;
  avg_response_ms: number | null;
  total_nodes_executed: number;
  rag_used_count: number;
  thumbs_up_count: number;
  thumbs_down_count: number;
}

const AgentPerformancePage = () => {
  const [dateRange, setDateRange] = useState<DateRange | undefined>({
    from: subDays(new Date(), 7),
    to: new Date(),
  });
  const [periodPreset, setPeriodPreset] = useState<PeriodPreset>("last7days");

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
  const { comparisonRange, comparedWithLabel } = useAnalyticsPeriodComparison(
    dateRange,
    periodPreset,
  );

  const handleDateRangeChange = useCallback(
    (range: DateRange | undefined, meta?: { preset: PeriodPreset }) => {
      setDateRange(range);
      if (meta?.preset) {
        setPeriodPreset(meta.preset);
      } else if (range) {
        setPeriodPreset("custom");
      }
    },
    [],
  );
  const [summary, setSummary] = useState<AgentStatsSummaryResponse | null>(null);
  const [previousSummary, setPreviousSummary] = useState<AgentStatsSummaryResponse | null>(null);
  const [items, setItems] = useState<AgentDailyStatsItem[]>([]);
  const [compareItems, setCompareItems] = useState<AgentDailyStatsItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedItem, setSelectedItem] = useState<AgentDailyStatsItem | null>(null);

  // Escalation node config
  const [nodeBreakdown, setNodeBreakdown] = useState<NodeTypeBreakdownItem[]>([]);
  const [escalationNode, setEscalationNode] = useState<string>("");

  const loadData = async (
    range: DateRange | undefined,
    filters: { agent_id?: string; group_id?: string },
    compareRange: DateRange | undefined,
  ) => {
    setLoading(true);
    setError(null);
    try {
      const { from_date, to_date } = toExpandedUTCDateRange(range);
      const params = {
        from_date,
        to_date,
        ...filters,
      };
      const compareParams = compareRange?.from && compareRange?.to
        ? {
            ...toExpandedUTCDateRange(compareRange),
            ...filters,
          }
        : undefined;

      const [currentData, previousData, dailyData, compareDailyData] = await Promise.all([
        fetchAgentStatsSummary(params),
        compareParams ? fetchAgentStatsSummary(compareParams) : Promise.resolve(null),
        fetchAgentDailyStats(params),
        compareParams ? fetchAgentDailyStats(compareParams) : Promise.resolve(null),
      ]);
      setSummary(currentData);
      setPreviousSummary(previousData);
      setItems(dailyData?.items ?? []);
      setCompareItems(compareDailyData?.items ?? []);
    } catch {
      setError("Failed to load analytics data.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData(dateRange, filterParams, comparisonRange);

    if (agentFilter !== "all") {
      setEscalationNode(localStorage.getItem(LS_KEY(agentFilter)) ?? "");
      fetchAgentNodeBreakdown(agentFilter, toExpandedUTCDateRange(dateRange))
        .then((data) => setNodeBreakdown(data?.items ?? []))
        .catch(() => setNodeBreakdown([]));
    } else {
      setEscalationNode("");
      setNodeBreakdown([]);
    }
  }, [
    dateRange,
    agentFilter,
    filterParams.agent_id,
    filterParams.group_id,
    comparisonRange,
  ]);

  const handleEscalationNodeChange = (value: string) => {
    setEscalationNode(value);
    if (agentFilter !== "all") {
      if (value) {
        localStorage.setItem(LS_KEY(agentFilter), value);
      } else {
        localStorage.removeItem(LS_KEY(agentFilter));
      }
    }
  };

  // Derived escalation metrics (conversation-based)
  const escalationItem = nodeBreakdown.find((n) => n.node_type === escalationNode);
  const totalConversations = summary?.total_unique_conversations ?? 0;

  const escalationRate =
    escalationItem && totalConversations > 0
      ? escalationItem.unique_conversations / totalConversations
      : null;
  const containmentRate = escalationRate !== null ? 1 - escalationRate : null;

  const conversationStatusByAgent = useMemo(() => {
    const map = new Map<string, { unique_conversations: number; finalized_conversations: number; in_progress_conversations: number }>();
    for (const row of summary?.conversation_status_by_agent ?? []) {
      map.set(row.agent_id, {
        unique_conversations: row.unique_conversations,
        finalized_conversations: row.finalized_conversations,
        in_progress_conversations: row.in_progress_conversations,
      });
    }
    return map;
  }, [summary?.conversation_status_by_agent]);

  // When all agents shown: aggregate daily rows into one row per agent
  const aggregatedItems = useMemo<AgentAggregated[]>(() => {
    const map = new Map<string, AgentAggregated & { _totalMs: number; _msCount: number }>();
    for (const item of items) {
      const existing = map.get(item.agent_id);
      if (existing) {
        existing.execution_count += item.execution_count;
        existing.success_count += item.success_count;
        existing.error_count += item.error_count;
        existing.total_nodes_executed += item.total_nodes_executed;
        existing.rag_used_count += item.rag_used_count;
        existing.thumbs_up_count += item.thumbs_up_count;
        existing.thumbs_down_count += item.thumbs_down_count;
        if (item.avg_response_ms != null) {
          existing._totalMs += item.avg_response_ms * item.execution_count;
          existing._msCount += item.execution_count;
        }
      } else {
        map.set(item.agent_id, {
          id: item.agent_id,
          agent_id: item.agent_id,
          unique_conversations: item.unique_conversations,
          finalized_conversations: item.finalized_conversations,
          in_progress_conversations: item.in_progress_conversations,
          execution_count: item.execution_count,
          success_count: item.success_count,
          error_count: item.error_count,
          avg_response_ms: item.avg_response_ms,
          total_nodes_executed: item.total_nodes_executed,
          rag_used_count: item.rag_used_count,
          thumbs_up_count: item.thumbs_up_count,
          thumbs_down_count: item.thumbs_down_count,
          _totalMs: item.avg_response_ms != null ? item.avg_response_ms * item.execution_count : 0,
          _msCount: item.avg_response_ms != null ? item.execution_count : 0,
        });
      }
    }
    return Array.from(map.values()).map((a) => {
      const conv = conversationStatusByAgent.get(a.agent_id);
      return {
        ...a,
        unique_conversations: conv?.unique_conversations ?? a.unique_conversations,
        finalized_conversations: conv?.finalized_conversations ?? a.finalized_conversations,
        in_progress_conversations: conv?.in_progress_conversations ?? a.in_progress_conversations,
        avg_response_ms: a._msCount > 0 ? a._totalMs / a._msCount : null,
      };
    });
  }, [items, conversationStatusByAgent]);

  const statsColumns = useMemo(() => {
    const statCols: Column<AgentAggregated>[] = [
      {
        header: "Conversations",
        key: "unique_conversations",
        description: "Unique chat sessions in the period.",
        cell: (item: AgentAggregated) => (
          <div className="flex flex-col gap-0.5">
            <span className="font-medium">{item.unique_conversations.toLocaleString()}</span>
            {(item.finalized_conversations + item.in_progress_conversations) > 0 && (
              <span className="text-xs text-muted-foreground/70">
                {item.finalized_conversations} completed · {item.in_progress_conversations} in progress
              </span>
            )}
          </div>
        ),
      },
      {
        header: "Success Rate",
        key: "success_count",
        description: "Percentage of executions that completed without errors.",
        cell: (item: AgentAggregated) => {
          const rate = item.execution_count > 0
            ? ((item.success_count / item.execution_count) * 100).toFixed(1)
            : "0.0";
          const hasErrors = item.error_count > 0;
          return (
            <div className="flex flex-col gap-0.5">
              <span className={`font-medium ${hasErrors ? "text-amber-600" : "text-emerald-600"}`}>
                {rate}%
              </span>
              <span className="text-xs text-muted-foreground/70">
                {item.success_count} of {item.execution_count}
              </span>
            </div>
          );
        },
      },
      {
        header: "Avg Response",
        key: "avg_response_ms",
        description: "Average time from request to response.",
        cell: (item: AgentAggregated) => (
          <span className={item.avg_response_ms != null ? getResponseTimeColor(item.avg_response_ms) + " font-medium" : "text-zinc-400"}>
            {formatResponseTime(item.avg_response_ms)}
          </span>
        ),
      },
      {
        header: <ThumbsUp className="w-4 h-4 text-emerald-600" />,
        key: "thumbs_up_count",
        description: "Positive feedback from users.",
        cell: (item: AgentAggregated) => (
          <span className="text-emerald-600 font-medium">
            {item.thumbs_up_count.toLocaleString()}
          </span>
        ),
      },
      {
        header: <ThumbsDown className="w-4 h-4 text-rose-500" />,
        key: "thumbs_down_count",
        description: "Negative feedback from users.",
        cell: (item: AgentAggregated) => (
          <span className={item.thumbs_down_count > 0 ? "text-rose-500 font-medium" : "text-zinc-400"}>
            {item.thumbs_down_count.toLocaleString()}
          </span>
        ),
      },
    ];

    if (agentFilter === "all") {
      return [
        {
          header: "Agent",
          key: "agent_id",
          cell: (item: AgentAggregated) => (
            <span className="text-sm font-medium text-zinc-700">
              {agentNameMap[item.agent_id] ?? item.agent_id.slice(0, 8) + "…"}
            </span>
          ),
        },
        ...statCols,
      ];
    }

    // Single agent: show per-day rows with date column
    return [
      {
        header: "Date",
        key: "stat_date",
        cell: (item: AgentAggregated) => (
          <span className="text-xs text-zinc-500">
            {new Date((item as unknown as AgentDailyStatsItem).stat_date + "T00:00:00").toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}
          </span>
        ),
      },
      ...statCols,
    ];
  }, [agentFilter, agentNameMap]);

  const exportParams = {
    ...filterParams,
    ...toExpandedUTCDateRange(dateRange),
  };

  const hasSummary = summary != null;
  const hasDailyStats = items.length > 0;
  const showDetailSections = hasSummary || hasDailyStats;
  const exportRowCount =
    agentFilter === "all" ? aggregatedItems.length : items.length;
  const canExport = !loading && exportRowCount > 0;

  return (
    <SidebarProvider>
      <div className="min-h-screen flex w-full overflow-x-hidden">
        <AppSidebar />
        <main className="flex-1 flex flex-col bg-zinc-100 min-w-0 relative peer-data-[state=expanded]:md:ml-[calc(var(--sidebar-width)-2px)] peer-data-[state=collapsed]:md:ml-0 transition-[margin] duration-200">
          <SidebarTrigger className="fixed top-6 z-10 h-8 w-8 bg-white/50 backdrop-blur-sm hover:bg-white/70 rounded-full shadow-md transition-[left] duration-200" />
          <div className="flex-1 p-4 sm:p-6 lg:p-8">
            <div className="max-w-7xl mx-auto space-y-6">

              <AnalyticsPageHeader
                title="Agent Performance"
                subtitle="Daily performance metrics per agent"
              >
                <AnalyticsFilters
                  groups={showGroupFilter ? groups : undefined}
                  groupFilter={groupFilter}
                  onGroupFilterChange={setGroupFilter}
                  agents={agents}
                  agentFilter={agentFilter}
                  onAgentFilterChange={setAgentFilter}
                  dateRange={dateRange}
                  onDateRangeChange={handleDateRangeChange}
                >
                  <ExportButton
                    endpoint="/analytics/agents/export"
                    params={exportParams}
                    filename="agent-performance"
                    disabled={!canExport}
                  />
                </AnalyticsFilters>
              </AnalyticsPageHeader>

              {loading ? (
                <AgentPerformancePageSkeleton tableColumns={statsColumns.length} />
              ) : (
                <div className="space-y-6 sm:space-y-8">
              {!showDetailSections && !error && <AnalyticsAggregatedDataEmptyState />}

              {/* Summary KPIs — always shown when summary API returns data */}
              <SummaryStatsCards
                summary={summary}
                previousSummary={previousSummary}
                comparedWithLabel={comparedWithLabel}
                loading={false}
                error={error}
                containmentRate={containmentRate}
              />

              {/* Escalation tracking — only when a specific agent is selected */}
              {summary && agentFilter !== "all" && (
                <div className={cn("space-y-3", analyticsFadeUpClass)}>
                  {/* Escalation node config */}
                  <div className="flex items-center gap-3 flex-wrap">
                    <div className="flex items-center gap-1.5 text-xs text-zinc-500">
                      <Settings2 className="w-3.5 h-3.5" />
                      <span>Escalation node:</span>
                    </div>
                    <Select
                      value={escalationNode || "__none__"}
                      onValueChange={(v) => handleEscalationNodeChange(v === "__none__" ? "" : v)}
                    >
                      <SelectTrigger className="w-56 h-8 text-xs">
                        <SelectValue placeholder="Select node to track…" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="__none__">
                          <span className="text-muted-foreground">None configured</span>
                        </SelectItem>
                        {nodeBreakdown.map((n) => (
                          <SelectItem key={n.node_type} value={n.node_type}>
                            {nodeTypeLabel(n.node_type)}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>

                  {/* Escalation / Containment detail cards */}
                  {escalationRate !== null && (
                    <div className="grid grid-cols-2 gap-4">
                      {/* Trigger Rate */}
                      <div className="bg-white rounded-xl border-t-2 border-orange-400 border-x border-b border-border p-4 flex flex-col gap-3">
                        <div className="flex items-center justify-between">
                          <p className="text-xs text-muted-foreground">Escalation Rate</p>
                          <TrendingDown className="w-3.5 h-3.5 text-orange-400" />
                        </div>
                        <p className="text-3xl font-bold text-zinc-900 leading-none">
                          {(escalationRate * 100).toFixed(1)}%
                        </p>
                        <div className="space-y-1">
                          <div className="w-full h-1.5 bg-zinc-100 rounded-full overflow-hidden">
                            <div
                              className="h-full bg-orange-400 rounded-full transition-all duration-500"
                              style={{ width: `${(escalationRate * 100).toFixed(1)}%` }}
                            />
                          </div>
                          <p className="text-xs text-muted-foreground">
                            {escalationItem!.unique_conversations.toLocaleString()} of {totalConversations.toLocaleString()} conversations escalated to <span className="font-medium text-zinc-600">{nodeTypeLabel(escalationNode)}</span>
                          </p>
                          <div className="flex items-center gap-3 pt-1">
                            <span className="flex items-center gap-1 text-xs text-emerald-600">
                              <ThumbsUp className="w-3 h-3" />
                              {escalationItem!.thumbs_up_count.toLocaleString()}
                            </span>
                            <span className="flex items-center gap-1 text-xs text-rose-500">
                              <ThumbsDown className="w-3 h-3" />
                              {escalationItem!.thumbs_down_count.toLocaleString()}
                            </span>
                          </div>
                        </div>
                      </div>

                      {/* Containment Rate */}
                      <div className="bg-white rounded-xl border-t-2 border-teal-400 border-x border-b border-border p-4 flex flex-col gap-3">
                        <div className="flex items-center justify-between">
                          <p className="text-xs text-muted-foreground">Containment Rate</p>
                          <ShieldCheck className="w-3.5 h-3.5 text-teal-500" />
                        </div>
                        <p className="text-3xl font-bold text-zinc-900 leading-none">
                          {(containmentRate! * 100).toFixed(1)}%
                        </p>
                        <div className="space-y-1">
                          <div className="w-full h-1.5 bg-zinc-100 rounded-full overflow-hidden">
                            <div
                              className="h-full bg-teal-400 rounded-full transition-all duration-500"
                              style={{ width: `${(containmentRate! * 100).toFixed(1)}%` }}
                            />
                          </div>
                          <p className="text-xs text-muted-foreground">
                            Conversations resolved without escalation
                          </p>
                          <div className="flex items-center gap-3 pt-1">
                            <span className="flex items-center gap-1 text-xs text-emerald-600">
                              <ThumbsUp className="w-3 h-3" />
                              {Math.max(0, (summary?.total_thumbs_up ?? 0) - escalationItem!.thumbs_up_count).toLocaleString()}
                            </span>
                            <span className="flex items-center gap-1 text-xs text-rose-500">
                              <ThumbsDown className="w-3 h-3" />
                              {Math.max(0, (summary?.total_thumbs_down ?? 0) - escalationItem!.thumbs_down_count).toLocaleString()}
                            </span>
                          </div>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              )}

              {showDetailSections && (
                <>
                  <AgentExecutionChart
                    items={items}
                    compareItems={compareItems}
                    dateRange={dateRange}
                    comparisonRange={comparisonRange}
                    comparedWithLabel={comparedWithLabel}
                    loading={false}
                    agentNameMap={agentNameMap}
                  />

                  <div className={analyticsFadeUpClass}>
                    <DataTable
                      data={
                        agentFilter === "all"
                          ? aggregatedItems
                          : (items as unknown as AgentAggregated[])
                      }
                      columns={statsColumns as Column<AgentAggregated>[]}
                      loading={false}
                      error={error}
                      emptyState={<AgentPerformanceTableEmptyState />}
                      keyExtractor={(item) => item.id}
                      pageSize={10}
                      onRowClick={
                        agentFilter !== "all"
                          ? (item) => setSelectedItem(item as unknown as AgentDailyStatsItem)
                          : undefined
                      }
                    />
                  </div>
                </>
              )}
                </div>
              )}

            </div>
          </div>
        </main>
      </div>

      {selectedItem && (
        <AgentNodeBreakdownDialog
          open={!!selectedItem}
          onClose={() => setSelectedItem(null)}
          agentId={selectedItem.agent_id}
          agentName={agentNameMap[selectedItem.agent_id] ?? selectedItem.agent_id.slice(0, 8) + "…"}
          totalExecutions={selectedItem.execution_count}
          fromDate={toExpandedUTCDateRange(dateRange).from_date}
          toDate={toExpandedUTCDateRange(dateRange).to_date}
        />
      )}
    </SidebarProvider>
  );
};

export default AgentPerformancePage;
