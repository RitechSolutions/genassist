import { ChevronDown, SlidersHorizontal } from "lucide-react";
import { Badge } from "@/components/badge";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuTrigger,
} from "@/components/dropdown-menu";
import { cn } from "@/helpers/utils";
import type { UserGroup } from "@/interfaces/userGroup.interface";

export const ALL_FILTER_VALUE = "all";

export interface AnalyticsFilterOption {
  value: string;
  label: string;
}

export interface AnalyticsFilterGroup {
  key: string;
  label: string;
  allLabel: string;
  value: string;
  options: AnalyticsFilterOption[];
  onChange: (value: string) => void;
}

interface AnalyticsFilterMenuProps {
  /** Group filter (admins) — omit `groups`/`onGroupFilterChange` to hide the Group submenu */
  groups?: UserGroup[];
  groupFilter?: string;
  onGroupFilterChange?: (value: string) => void;

  agents: Array<{ id: string; name: string }>;
  agentFilter: string;
  onAgentFilterChange: (value: string) => void;

  /** Page-specific filters rendered as submenus after Agent (e.g. Model, Node type). */
  extraGroups?: AnalyticsFilterGroup[];
}

/**
 * Group, agent and any page-specific filters collapsed into a single pill menu with an
 * active-count badge. The shared Analytics filter control used across Cost Explorer, AI
 * Insights, Agent Performance and Node Analytics.
 */
export function AnalyticsFilterMenu({
  groups,
  groupFilter,
  onGroupFilterChange,
  agents,
  agentFilter,
  onAgentFilterChange,
  extraGroups = [],
}: AnalyticsFilterMenuProps) {
  const filterGroups: AnalyticsFilterGroup[] = [
    ...(groups && onGroupFilterChange
      ? [
          {
            key: "group",
            label: "Group",
            allLabel: "All groups",
            value: groupFilter ?? ALL_FILTER_VALUE,
            options: groups.map((g) => ({ value: g.id, label: g.name })),
            onChange: onGroupFilterChange,
          },
        ]
      : []),
    {
      key: "agent",
      label: "Agent",
      allLabel: "All agents",
      value: agentFilter,
      options: agents.map((a) => ({ value: a.id, label: a.name })),
      onChange: onAgentFilterChange,
    },
    ...extraGroups,
  ];

  const activeCount = filterGroups.filter((g) => g.value !== ALL_FILTER_VALUE).length;
  const selectedLabel = (group: AnalyticsFilterGroup) =>
    group.options.find((o) => o.value === group.value)?.label ?? group.value;

  const clearAll = () => {
    // Reset in array order (group before agent) so a parent filter that also clears its
    // dependants — setGroupFilter resets the agent — cannot clobber a value set after it.
    for (const group of filterGroups) group.onChange(ALL_FILTER_VALUE);
  };

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          aria-label={`Filters${activeCount > 0 ? `, ${activeCount} active` : ""}`}
          className={cn(
            "flex h-9 shrink-0 items-center gap-1.5 rounded-full border px-3 text-xs ring-offset-background transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-1 max-md:w-full xl:h-10 xl:text-sm",
            activeCount > 0
              ? "border-primary/30 bg-primary/5 text-foreground"
              : "border-input bg-card text-muted-foreground hover:bg-muted"
          )}
        >
          <SlidersHorizontal className="h-3.5 w-3.5 shrink-0" />
          <span>Filters</span>
          {activeCount > 0 && (
            <span className="flex h-4 min-w-[16px] items-center justify-center rounded-full bg-primary px-1 text-[10px] font-medium text-primary-foreground">
              {activeCount}
            </span>
          )}
          <ChevronDown className="ml-auto h-3 w-3 shrink-0 opacity-50" />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="min-w-[14rem]">
        {filterGroups.map((group) => (
          <DropdownMenuSub key={group.key}>
            <DropdownMenuSubTrigger className="flex items-center gap-2">
              <span className="shrink-0">{group.label}</span>
              {group.value !== ALL_FILTER_VALUE && (
                <Badge variant="outline" className="ml-auto max-w-[9rem] truncate px-1 py-0 text-[10px]">
                  {selectedLabel(group)}
                </Badge>
              )}
            </DropdownMenuSubTrigger>
            <DropdownMenuSubContent className="max-h-64 max-w-[16rem] overflow-y-auto">
              <DropdownMenuItem onClick={() => group.onChange(ALL_FILTER_VALUE)}>
                <span className="truncate">{group.allLabel}</span>
                {group.value === ALL_FILTER_VALUE && <span className="ml-auto pl-2">✓</span>}
              </DropdownMenuItem>
              {group.options.length === 0 ? (
                <DropdownMenuItem disabled>No options available</DropdownMenuItem>
              ) : (
                group.options.map((option) => (
                  <DropdownMenuItem key={option.value} onClick={() => group.onChange(option.value)}>
                    <span className="truncate" title={option.label}>
                      {option.label}
                    </span>
                    {group.value === option.value && <span className="ml-auto pl-2">✓</span>}
                  </DropdownMenuItem>
                ))
              )}
            </DropdownMenuSubContent>
          </DropdownMenuSub>
        ))}
        {activeCount > 0 && (
          <>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={clearAll} className="text-muted-foreground">
              Clear filters
            </DropdownMenuItem>
          </>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
