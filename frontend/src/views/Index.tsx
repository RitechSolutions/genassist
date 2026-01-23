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
import { useState } from "react";
import { KPISection } from "./Analytics";
import { ActiveConversations } from "./ActiveConversations/pages/ActiveConversations";

const timeFilters = [
  { label: "Today", value: "today" },
  { label: "Last 7 Days", value: "7days" },
  { label: "Last 30 Days", value: "30days" },
  { label: "Last 6 Months", value: "6months" },
  { label: "Last 12 Months", value: "12months" },
];

const Index = () => {
  const [timeFilter, setTimeFilter] = useState("30days");
  const isMobile = useIsMobile();

  return (
    <SidebarProvider>
      <div className="min-h-screen flex w-full overflow-x-hidden">
        {!isMobile && <AppSidebar />}
        <main className="flex-1 flex flex-col bg-zinc-100 min-w-0 relative peer-data-[state=expanded]:md:ml-[calc(var(--sidebar-width)-2px)] peer-data-[state=collapsed]:md:ml-0 transition-[margin] duration-200">
          <SidebarTrigger className="fixed top-4 z-10 h-8 w-8 bg-white/50 backdrop-blur-sm hover:bg-white/70 rounded-full shadow-md transition-[left] duration-200" />
          <div className="flex-1 p-4 sm:p-6 lg:p-8">
            <div className="max-w-7xl mx-auto w-full">
              <header className="mb-6 sm:mb-8">
                <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between sm:flex-wrap mb-2">
                  <h1 className="text-2xl md:text-3xl font-bold leading-tight animate-fade-down">
                    Dashboard
                  </h1>
                  <div className="w-full sm:w-auto">
                    <Select value={timeFilter} onValueChange={setTimeFilter}>
                      <SelectTrigger className="w-full sm:w-[180px]">
                        <SelectValue placeholder="Select time range" />
                      </SelectTrigger>
                      <SelectContent>
                        {timeFilters.map((filter) => (
                          <SelectItem key={filter.value} value={filter.value}>
                            {filter.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                <p className="text-sm md:text-base text-muted-foreground animate-fade-up">
                  Monitor and analyze your customer interactions in real-time
                </p>
              </header>

              <KPISection timeFilter={timeFilter} />
              <ActiveConversations />
            </div>
          </div>
        </main>
      </div>
    </SidebarProvider>
  );
};

export default Index;
