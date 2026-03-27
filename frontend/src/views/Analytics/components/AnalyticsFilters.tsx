import type { ReactNode } from "react";
import type { DateRange } from "react-day-picker";
import { DateRangePicker } from "@/components/date-range-picker";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/select";
import type { AgentListItem } from "@/interfaces/ai-agent.interface";

export interface AnalyticsFiltersProps {
  /** Agent filter — pass `undefined` to hide the agent selector */
  agents?: AgentListItem[];
  agentFilter?: string;
  onAgentFilterChange?: (value: string) => void;

  /** Date range picker */
  dateRange: DateRange | undefined;
  onDateRangeChange: (value: DateRange | undefined) => void;

  /** Optional comparison date range */
  compareDateRange?: DateRange | undefined;
  onCompareDateRangeChange?: (value: DateRange | undefined) => void;

  /** Optional extra controls rendered after the built-in filters (e.g. ExportButton, node type select) */
  children?: ReactNode;
}

export const AnalyticsFilters = ({
  agents,
  agentFilter,
  onAgentFilterChange,
  dateRange,
  onDateRangeChange,
  compareDateRange,
  onCompareDateRangeChange,
  children,
}: AnalyticsFiltersProps) => {
  return (
    <div className="flex flex-wrap items-center gap-2">
      {/* Agent selector */}
      {agents && onAgentFilterChange && (
        <Select value={agentFilter ?? "all"} onValueChange={onAgentFilterChange}>
          <SelectTrigger className="w-44">
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

      {/* Date range with presets */}
      <DateRangePicker value={dateRange} onChange={onDateRangeChange} />

      {/* Optional comparison date range */}
      {onCompareDateRangeChange && (
        <div className="flex items-center gap-1.5">
          <span className="text-xs text-muted-foreground whitespace-nowrap">vs</span>
          <DateRangePicker
            value={compareDateRange}
            onChange={onCompareDateRangeChange}
            placeholder="Compare period…"
          />
        </div>
      )}

      {/* Extra controls (export button, node type filter, etc.) */}
      {children}
    </div>
  );
};
