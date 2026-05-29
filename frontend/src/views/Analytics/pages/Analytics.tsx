import { useState } from "react";
import { subDays } from "date-fns";
import type { DateRange } from "react-day-picker";
import { SidebarProvider, SidebarTrigger } from "@/components/sidebar";
import { AppSidebar } from "@/layout/app-sidebar";
import { AnalyticsMetricsSection } from "../components/AnalyticsMetricsSection";
import { AnalyticsFilters } from "../components/AnalyticsFilters";
import { AnalyticsPageHeader } from "../components/AnalyticsPageHeader";
import { AnalyticsInsightsPageSkeleton } from "../components/skeletons";
import { AttributeBreakdownChart } from "../components/reports/AttributeBreakdownChart";
import { useAnalyticsData } from "../hooks/useAnalyticsData";
import { useAgentsList } from "../hooks/useAgentsList";

const AnalyticsPage = () => {
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
              <AnalyticsPageHeader
                title="AI Insights"
                subtitle="AI-generated metrics from conversation analysis"
              >
                <AnalyticsFilters
                  agents={agents}
                  agentFilter={agentFilter}
                  onAgentFilterChange={setAgentFilter}
                  dateRange={dateRange}
                  onDateRangeChange={setDateRange}
                  compareDateRange={compareDateRange}
                  onCompareDateRangeChange={setCompareDateRange}
                />
              </AnalyticsPageHeader>

              {loading ? (
                <AnalyticsInsightsPageSkeleton />
              ) : (
                <div className="space-y-6 sm:space-y-8">
                  <AnalyticsMetricsSection
                    dateRange={dateRange}
                    agentId={agentFilter}
                    metrics={metrics}
                    deltas={deltas}
                    loading={false}
                    refreshing={refreshing}
                    error={error}
                    compareDateRange={compareDateRange}
                  />

                  <AttributeBreakdownChart
                    agentId={agentFilter}
                    dateRange={dateRange}
                  />
                </div>
              )}
            </div>
          </div>
        </main>
      </div>
    </SidebarProvider>
  );
};

export default AnalyticsPage;
