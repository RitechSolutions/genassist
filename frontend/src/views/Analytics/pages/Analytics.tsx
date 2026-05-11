import { useState } from "react";
import { subDays } from "date-fns";
import type { DateRange } from "react-day-picker";
import { SidebarProvider, SidebarTrigger } from "@/components/sidebar";
import { AppSidebar } from "@/layout/app-sidebar";
import { useIsMobile } from "@/hooks/useMobile";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/select";
import { AnalyticsMetricsSection } from "../components/AnalyticsMetricsSection";
import { AnalyticsFilters } from "../components/AnalyticsFilters";
import { AttributeBreakdownChart } from "../components/reports/AttributeBreakdownChart";
import { useAnalyticsData } from "../hooks/useAnalyticsData";
import { useAgentsList } from "../hooks/useAgentsList";

const AnalyticsPage = () => {
  const isMobile = useIsMobile();
  const [dateRange, setDateRange] = useState<DateRange | undefined>({
    from: subDays(new Date(), 7),
    to: new Date(),
  });
  const [agentFilter, setAgentFilter] = useState("all");
  const [compareDateRange, setCompareDateRange] = useState<DateRange | undefined>(undefined);
  const { agents } = useAgentsList();
  const { metrics, deltas, loading, refreshing, error } = useAnalyticsData(dateRange, agentFilter, compareDateRange);

  return (
    <SidebarProvider>
      <div className="min-h-screen flex w-full overflow-x-hidden">
        <AppSidebar />
        <main className="flex-1 flex flex-col bg-zinc-100 min-w-0 relative peer-data-[state=expanded]:md:ml-[calc(var(--sidebar-width)-2px)] peer-data-[state=collapsed]:md:ml-0 transition-[margin] duration-200">
          <SidebarTrigger className="fixed top-6 z-10 h-8 w-8 bg-white/50 backdrop-blur-sm hover:bg-white/70 rounded-full shadow-md transition-[left] duration-200" />
          <div className="flex-1 p-4 sm:p-6 lg:p-8">
            <div className="max-w-7xl mx-auto">
              <header className="mb-6 sm:mb-8">
                <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                  <div className="min-w-0">
                    <div className="mb-1 flex items-center justify-between gap-3 sm:mb-2">
                      <h1 className="text-2xl sm:text-3xl font-bold animate-fade-down">AI Insights</h1>
                      {isMobile && (
                        <Select value={agentFilter} onValueChange={setAgentFilter}>
                          <SelectTrigger className="w-44 rounded-full">
                            <SelectValue placeholder="All agents" />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="all">All agents</SelectItem>
                            {agents.map((a) => (
                              <SelectItem key={a.id} value={a.id}>
                                {a.name}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      )}
                    </div>
                    <p className="text-sm sm:text-base text-muted-foreground animate-fade-up">
                      AI-generated metrics from conversation analysis
                    </p>
                  </div>
                  {!isMobile && (
                    <AnalyticsFilters
                      agents={agents}
                      agentFilter={agentFilter}
                      onAgentFilterChange={setAgentFilter}
                      dateRange={dateRange}
                      onDateRangeChange={setDateRange}
                      compareDateRange={compareDateRange}
                      onCompareDateRangeChange={setCompareDateRange}
                    />
                  )}
                </div>
                {isMobile && (
                  <div className="mt-3">
                    <AnalyticsFilters
                      className="flex-wrap"
                      compactDatePickers
                      dateRange={dateRange}
                      onDateRangeChange={setDateRange}
                      compareDateRange={compareDateRange}
                      onCompareDateRangeChange={setCompareDateRange}
                    />
                  </div>
                )}
              </header>

              <AnalyticsMetricsSection
                dateRange={dateRange}
                agentId={agentFilter}
                metrics={metrics}
                deltas={deltas}
                loading={loading}
                refreshing={refreshing}
                error={error}
                compareDateRange={compareDateRange}
              />

              <AttributeBreakdownChart
                agentId={agentFilter}
                dateRange={dateRange}
              />
            </div>
          </div>
        </main>
      </div>
    </SidebarProvider>
  );
};

export default AnalyticsPage;
