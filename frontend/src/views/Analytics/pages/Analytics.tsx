import { useState } from "react";
import { SidebarProvider } from "@/components/sidebar";
import { AppSidebar } from "@/layout/app-sidebar";
import { useIsMobile } from "@/hooks/useMobile";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/select";
import { MetricsSection } from "../components/MetricsSection";
import { useAnalyticsData } from "../hooks/useAnalyticsData";

const AnalyticsPage = () => {
  const [timeFrame, setTimeFrame] = useState("7days");
  const { metrics, loading, error } = useAnalyticsData();
  const isMobile = useIsMobile();

  return (
    <SidebarProvider>
      <div className="min-h-screen flex w-full">
        {!isMobile && <AppSidebar />}
        <main className="flex-1 flex flex-col bg-zinc-100 min-h-screen overflow-x-hidden">
          <div className="flex-1 px-4 sm:px-6 lg:px-8 py-4 sm:py-6 lg:py-8">
            <div className="max-w-7xl mx-auto">
              <header className="mb-6 sm:mb-8 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                <div>
                  <h1 className="text-2xl sm:text-3xl font-bold mb-1 sm:mb-2 animate-fade-down">Analytics</h1>
                  <p className="text-sm sm:text-base text-muted-foreground animate-fade-up">Track and analyze your performance metrics</p>
                </div>
                <Select 
                  defaultValue="7days" 
                  onValueChange={setTimeFrame}
                >
                  <SelectTrigger className="w-full sm:w-[180px]">
                    <SelectValue placeholder="Select time period" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="today">Today</SelectItem>
                    <SelectItem value="7days">Last 7 Days</SelectItem>
                    <SelectItem value="30days">Last 30 Days</SelectItem>
                    <SelectItem value="6months">Last 6 Months</SelectItem>
                    <SelectItem value="12months">Last 12 Months</SelectItem>
                  </SelectContent>
                </Select>
              </header>

              <MetricsSection 
                timeFrame={timeFrame} 
                metrics={metrics} 
                loading={loading} 
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