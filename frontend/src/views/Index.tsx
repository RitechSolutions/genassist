import { SidebarProvider, SidebarTrigger } from "@/components/sidebar";
import { AppSidebar } from "@/layout/app-sidebar";
import { DateRangePicker } from "@/components/date-range-picker";
import { useState } from "react";
import { subDays, differenceInCalendarDays } from "date-fns";
import type { DateRange } from "react-day-picker";
import { KPISection } from "./Analytics";
import { ActiveConversations } from "./ActiveConversations/pages/ActiveConversations";

const Index = () => {
  const [dateRange, setDateRange] = useState<DateRange | undefined>({
    from: subDays(new Date(), 30),
    to: new Date(),
  });

  const selectedDays = (() => {
    if (!dateRange?.from) return 30;
    const toDate = dateRange.to ?? new Date();
    return Math.max(1, differenceInCalendarDays(toDate, dateRange.from) + 1);
  })();

  return (
    <SidebarProvider>
      <div className="min-h-screen flex w-full overflow-x-hidden">
        <AppSidebar />
        <main className="flex-1 flex flex-col bg-zinc-100 min-w-0 relative peer-data-[state=expanded]:md:ml-[calc(var(--sidebar-width)-2px)] peer-data-[state=collapsed]:md:ml-0 transition-[margin] duration-200">
          <SidebarTrigger className="fixed top-6 z-10 h-8 w-8 bg-white/50 backdrop-blur-sm hover:bg-white/70 rounded-full shadow-md transition-[left] duration-200" />
          <div className="flex-1 p-4 sm:p-6 lg:p-8">
            <div className="max-w-7xl mx-auto w-full">
              <header className="mb-6 sm:mb-8">
                <div className="mb-2 flex items-center justify-between gap-3">
                  <h1 className="text-2xl md:text-3xl font-bold leading-tight animate-fade-down">
                    Dashboard
                  </h1>
                  <DateRangePicker
                    value={dateRange}
                    onChange={setDateRange}
                    align="end"
                  />
                </div>
                <p className="text-sm md:text-base text-muted-foreground animate-fade-up">
                  Monitor and analyze your customer interactions in real-time
                </p>
              </header>

              <KPISection days={selectedDays} />
              <ActiveConversations />
            </div>
          </div>
        </main>
      </div>
    </SidebarProvider>
  );
};

export default Index;
