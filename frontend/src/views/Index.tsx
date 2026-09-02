import { DateRangePicker } from "@/components/date-range-picker";
import { subDays } from "date-fns";
import { usePersistedDateRange } from "@/hooks/usePersistedDateRange";
import { KPISection } from "./Analytics";
import { ActiveConversations } from "./ActiveConversations/pages/ActiveConversations";

const Index = () => {
  const [dateRange, setDateRange] = usePersistedDateRange({
    from: subDays(new Date(), 30),
    to: new Date(),
  });

  return (
    <>
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

              <KPISection dateRange={dateRange} />
              <ActiveConversations />
            </div>
          </div>
    </>
  );
};

export default Index;
