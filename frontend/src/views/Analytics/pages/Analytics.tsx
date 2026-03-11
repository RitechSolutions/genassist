import { useState } from "react";
import { subDays } from "date-fns";
import type { DateRange } from "react-day-picker";
import { SidebarProvider, SidebarTrigger } from "@/components/sidebar";
import { AppSidebar } from "@/layout/app-sidebar";
import { useIsMobile } from "@/hooks/useMobile";
import { AnalyticsMetricsSection } from "../components/AnalyticsMetricsSection";
import { AnalyticsFilters } from "../components/AnalyticsFilters";
import { useAnalyticsData } from "../hooks/useAnalyticsData";
import { useAgentsList } from "../hooks/useAgentsList";

const AnalyticsPage = () => {
  const isMobile = useIsMobile();
  const [dateRange, setDateRange] = useState<DateRange | undefined>({
    from: subDays(new Date(), 7),
    to: new Date(),
  });
  const [agentFilter, setAgentFilter] = useState("all");
  const { agents } = useAgentsList();
  const { metrics, deltas, loading, refreshing, error } = useAnalyticsData(dateRange, agentFilter);

  return (
    <SidebarProvider>
      <div className="min-h-screen flex w-full overflow-x-hidden">
        {!isMobile && <AppSidebar />}
        <main className="flex-1 flex flex-col bg-zinc-100 min-w-0 relative peer-data-[state=expanded]:md:ml-[calc(var(--sidebar-width)-2px)] peer-data-[state=collapsed]:md:ml-0 transition-[margin] duration-200">
          <SidebarTrigger className="fixed top-4 z-10 h-8 w-8 bg-white/50 backdrop-blur-sm hover:bg-white/70 rounded-full shadow-md transition-[left] duration-200" />
          <div className="flex-1 p-4 sm:p-6 lg:p-8">
            <div className="max-w-7xl mx-auto">
              <header className="mb-6 sm:mb-8 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                <div>
                  <h1 className="text-2xl sm:text-3xl font-bold mb-1 sm:mb-2 animate-fade-down">AI Insights</h1>
                  <p className="text-sm sm:text-base text-muted-foreground animate-fade-up">AI-generated metrics from conversation analysis</p>
                </div>
                <AnalyticsFilters
                  agents={agents}
                  agentFilter={agentFilter}
                  onAgentFilterChange={setAgentFilter}
                  dateRange={dateRange}
                  onDateRangeChange={setDateRange}
                />
              </header>

              <AnalyticsMetricsSection
                dateRange={dateRange}
                agentId={agentFilter}
                metrics={metrics}
                deltas={deltas}
                loading={loading}
                refreshing={refreshing}
                error={error}
              />
            </div>
          </div>
        </main>
      </div>
    </SidebarProvider>
  );
};

export default AnalyticsPage;
