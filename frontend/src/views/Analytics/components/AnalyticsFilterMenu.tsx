import {
  ALL_FILTER_VALUE,
  FilterMenu,
  type FilterMenuOption,
  type FilterMenuSelectGroup,
} from "@/components/FilterMenu";
import type { UserGroup } from "@/interfaces/userGroup.interface";

export { ALL_FILTER_VALUE };
export type AnalyticsFilterOption = FilterMenuOption;
export type AnalyticsFilterGroup = FilterMenuSelectGroup;

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

  return <FilterMenu groups={filterGroups} />;
}
