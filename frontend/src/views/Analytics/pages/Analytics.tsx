import { subDays } from "date-fns";
import { usePersistedDateRange, COMPARE_DATE_RANGE_STORAGE_KEY } from "@/hooks/usePersistedDateRange";
import { SidebarProvider, SidebarTrigger } from "@/components/sidebar";
import { AppSidebar } from "@/layout/app-sidebar";
import { AnalyticsMetricsSection } from "../components/AnalyticsMetricsSection";
import { AnalyticsFilters } from "../components/AnalyticsFilters";
import { AnalyticsPageHeader } from "../components/AnalyticsPageHeader";
import { AnalyticsInsightsPageSkeleton } from "../components/skeletons";
import { AttributeBreakdownChart } from "../components/reports/AttributeBreakdownChart";
import { useAnalyticsData } from "../hooks/useAnalyticsData";
import { useAnalyticsFilters } from "../hooks/useAnalyticsFilters";

const AnalyticsPage = () => {
  const [dateRange, setDateRange] = usePersistedDateRange({
    from: subDays(new Date(), 7),
    to: new Date(),
  });
  const [compareDateRange, setCompareDateRange] = usePersistedDateRange(
    undefined,
    COMPARE_DATE_RANGE_STORAGE_KEY,
  );
  const {
    groups,
    showGroupFilter,
    groupFilter,
    setGroupFilter,
    agentFilter,
    setAgentFilter,
    agents,
    filterParams,
  } = useAnalyticsFilters();

  const { metrics, deltas, loading, refreshing, error } = useAnalyticsData(
    dateRange,
    agentFilter,
    compareDateRange,
    filterParams.group_id,
  );

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
                  groups={showGroupFilter ? groups : undefined}
                  groupFilter={groupFilter}
                  onGroupFilterChange={setGroupFilter}
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
                    groupId={filterParams.group_id}
                    metrics={metrics}
                    deltas={deltas}
                    loading={false}
                    refreshing={refreshing}
                    error={error}
                    compareDateRange={compareDateRange}
                  />

                  <AttributeBreakdownChart
                    agentId={agentFilter}
                    groupId={filterParams.group_id}
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
