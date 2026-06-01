import type { ReactNode } from "react";
import type { DateRange } from "react-day-picker";
import { DateRangePicker, type DateRangePickerChangeMeta } from "@/components/date-range-picker";
import { cn } from "@/helpers/utils";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/select";
import type { AgentListItem } from "@/interfaces/ai-agent.interface";
import type { UserGroup } from "@/interfaces/userGroup.interface";

export interface AnalyticsFiltersProps {
  /** Group filter (admins) — pass `undefined` to hide */
  groups?: UserGroup[];
  groupFilter?: string;
  onGroupFilterChange?: (value: string) => void;

  /** Agent filter — pass `undefined` to hide the agent selector */
  agents?: AgentListItem[];
  agentFilter?: string;
  onAgentFilterChange?: (value: string) => void;

  /** Date range picker (single period control; comparison is derived automatically) */
  dateRange: DateRange | undefined;
  onDateRangeChange: (value: DateRange | undefined, meta?: DateRangePickerChangeMeta) => void;

  /** Optional extra controls rendered after the built-in filters (e.g. ExportButton, node type select) */
  children?: ReactNode;
  /** Optional wrapper class override */
  className?: string;
}

const datePickerTriggerClassName =
  "h-9 w-full min-w-0 gap-2 justify-start px-2.5 text-xs md:h-9 md:w-auto md:min-w-[150px] xl:min-w-[200px] xl:h-10 xl:px-4 xl:text-sm";

/** Shared select styling for analytics filter dropdowns (pill shape at all breakpoints). */
export const analyticsFilterSelectTriggerClassName =
  "w-full rounded-full md:w-36 xl:w-44";

export const AnalyticsFilters = ({
  groups,
  groupFilter,
  onGroupFilterChange,
  agents,
  agentFilter,
  onAgentFilterChange,
  dateRange,
  onDateRangeChange,
  children,
  className,
}: AnalyticsFiltersProps) => {
  return (
    <div
      className={cn(
        "flex w-full gap-2",
        "max-md:flex-col max-md:items-stretch",
        "md:flex-row md:flex-nowrap md:items-center",
        className,
      )}
    >
      {groups && onGroupFilterChange && (
        <Select value={groupFilter ?? "all"} onValueChange={onGroupFilterChange}>
          <SelectTrigger className={cn(analyticsFilterSelectTriggerClassName, "shrink-0")}>
            <SelectValue placeholder="All groups" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All groups</SelectItem>
            {groups.map((g) => (
              <SelectItem key={g.id} value={g.id}>
                {g.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      )}

      {agents && onAgentFilterChange && (
        <Select value={agentFilter ?? "all"} onValueChange={onAgentFilterChange}>
          <SelectTrigger className={cn(analyticsFilterSelectTriggerClassName, "shrink-0")}>
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

      <div className="min-w-0 max-md:w-full md:shrink-0">
        <DateRangePicker
          value={dateRange}
          onChange={onDateRangeChange}
          triggerClassName={datePickerTriggerClassName}
          disableFutureDates
        />
      </div>

      {children != null && (
        <div className="flex shrink-0 flex-col gap-2 max-md:w-full md:flex-row md:items-center [&_button]:max-md:w-full">
          {children}
        </div>
      )}
    </div>
  );
};
