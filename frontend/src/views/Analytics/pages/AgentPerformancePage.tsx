import { useEffect, useState, useMemo } from "react";
import { format, subDays } from "date-fns";
import { Settings2, TrendingDown, ShieldCheck, ThumbsUp, ThumbsDown } from "lucide-react";
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
import { SummaryStatsCards } from "../components/reports/SummaryStatsCards";
import { AgentExecutionChart } from "../components/reports/AgentExecutionChart";
import { AgentNodeBreakdownDialog } from "../components/reports/AgentNodeBreakdownDialog";
import { AnalyticsFilters } from "../components/AnalyticsFilters";
import { useAgentsList } from "../hooks/useAgentsList";
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
  const isMobile = useIsMobile();

  const [dateRange, setDateRange] = useState<DateRange | undefined>({
    from: subDays(new Date(), 7),
    to: new Date(),
  });
  const [agentFilter, setAgentFilter] = useState("all");
  const [compareDateRange, setCompareDateRange] = useState<DateRange | undefined>(undefined);

  const { agents, agentNameMap } = useAgentsList();
  const [summary, setSummary] = useState<AgentStatsSummaryResponse | null>(null);
  const [previousSummary, setPreviousSummary] = useState<AgentStatsSummaryResponse | null>(null);
  const [items, setItems] = useState<AgentDailyStatsItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedItem, setSelectedItem] = useState<AgentDailyStatsItem | null>(null);

  // Escalation node config
  const [nodeBreakdown, setNodeBreakdown] = useState<NodeTypeBreakdownItem[]>([]);
  const [escalationNode, setEscalationNode] = useState<string>("");

  const loadData = async (
    range: DateRange | undefined,
    agentId: string,
    compareRange: DateRange | undefined,
  ) => {
    setLoading(true);
    setError(null);
    try {
      const agentIdParam = agentId !== "all" ? agentId : undefined;
      const params = {
        from_date: range?.from ? format(range.from, "yyyy-MM-dd") : undefined,
        to_date: range?.to ? format(range.to, "yyyy-MM-dd") : undefined,
        agent_id: agentIdParam,
      };
      const compareParams = compareRange?.from && compareRange?.to
        ? {
            from_date: format(compareRange.from, "yyyy-MM-dd"),
            to_date: format(compareRange.to, "yyyy-MM-dd"),
            agent_id: agentIdParam,
          }
        : undefined;

      const [currentData, previousData, dailyData] = await Promise.all([
        fetchAgentStatsSummary(params),
        compareParams ? fetchAgentStatsSummary(compareParams) : Promise.resolve(null),
        fetchAgentDailyStats(params),
      ]);
      setSummary(currentData);
      setPreviousSummary(previousData);
      setItems(dailyData?.items ?? []);
    } catch {
      setError("Failed to load analytics data.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData(dateRange, agentFilter, compareDateRange);

    if (agentFilter !== "all") {
      setEscalationNode(localStorage.getItem(LS_KEY(agentFilter)) ?? "");
      fetchAgentNodeBreakdown(agentFilter, {
        from_date: dateRange?.from ? format(dateRange.from, "yyyy-MM-dd") : undefined,
        to_date: dateRange?.to ? format(dateRange.to, "yyyy-MM-dd") : undefined,
      })
        .then((data) => setNodeBreakdown(data?.items ?? []))
        .catch(() => setNodeBreakdown([]));
    } else {
      setEscalationNode("");
      setNodeBreakdown([]);
    }
  }, [dateRange, agentFilter, compareDateRange]);

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

  // When all agents shown: aggregate daily rows into one row per agent
  const aggregatedItems = useMemo<AgentAggregated[]>(() => {
    const map = new Map<string, AgentAggregated & { _totalMs: number; _msCount: number }>();
    for (const item of items) {
      const existing = map.get(item.agent_id);
      if (existing) {
        existing.unique_conversations += item.unique_conversations;
        existing.finalized_conversations += item.finalized_conversations;
        existing.in_progress_conversations += item.in_progress_conversations;
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
    return Array.from(map.values()).map((a) => ({
      ...a,
      avg_response_ms: a._msCount > 0 ? a._totalMs / a._msCount : null,
    }));
  }, [items]);

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
    agent_id: agentFilter !== "all" ? agentFilter : undefined,
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
                    Agent Performance
                  </h1>
                  <p className="text-sm text-muted-foreground animate-fade-up">
                    Daily performance metrics per agent
                  </p>
                </div>

                {/* Filters */}
                <AnalyticsFilters
                  agents={agents}
                  agentFilter={agentFilter}
                  onAgentFilterChange={setAgentFilter}
                  dateRange={dateRange}
                  onDateRangeChange={setDateRange}
                  compareDateRange={compareDateRange}
                  onCompareDateRangeChange={setCompareDateRange}
                >
                  <ExportButton
                    endpoint="/analytics/agents/export"
                    params={exportParams}
                    filename="agent-performance"
                    disabled={loading || items.length === 0}
                  />
                </AnalyticsFilters>
              </header>

              {/* Empty-data notice */}
              {!loading && items.length === 0 && !error && (
                <Card className="bg-blue-50 border-blue-200">
                  <CardContent className="p-4 flex items-center gap-3">
                    <Info className="w-5 h-5 text-blue-500 flex-shrink-0" />
                    <p className="text-sm text-blue-700">
                      No analytics data yet. Run the aggregation task to populate the summary tables.
                    </p>
                  </CardContent>
                </Card>
              )}

              {/* Summary cards — containment rate promoted to top-level KPI */}
              <SummaryStatsCards
                summary={summary}
                previousSummary={previousSummary}
                compareDateRange={compareDateRange}
                loading={loading}
                error={error}
                containmentRate={containmentRate}
              />

              {/* Escalation tracking — only when a specific agent is selected */}
              {agentFilter !== "all" && (
                <div className="space-y-3">
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

              {/* Daily conversations chart */}
              <AgentExecutionChart items={items} loading={loading} agentNameMap={agentNameMap} />

              {/* Stats table */}
              <div>
                <DataTable
                  data={agentFilter === "all" ? aggregatedItems : (items as unknown as AgentAggregated[])}
                  columns={statsColumns as Column<AgentAggregated>[]}
                  loading={loading}
                  error={error}
                  emptyMessage="No data for the selected period."
                  keyExtractor={(item) => item.id}
                  pageSize={10}
                  onRowClick={agentFilter !== "all" ? (item) => setSelectedItem(item as unknown as AgentDailyStatsItem) : undefined}
                />
              </div>

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
          fromDate={
            dateRange?.from ? format(dateRange.from, "yyyy-MM-dd") : undefined
          }
          toDate={
            dateRange?.to ? format(dateRange.to, "yyyy-MM-dd") : undefined
          }
        />
      )}
    </SidebarProvider>
  );
};

export default AgentPerformancePage;
