import { useCallback, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { currentUserIsAdmin } from "@/services/auth";
import { getAllUserGroups } from "@/services/userGroups";
import { fetchGroupAgents } from "@/services/analyticsReports";
import type { AnalyticsFilterParams } from "@/interfaces/analyticsReports.interface";
import type { UserGroup } from "@/interfaces/userGroup.interface";
import { useAgentsList } from "./useAgentsList";

export function useAnalyticsFilters() {
  const isAdmin = currentUserIsAdmin();
  const [groupFilter, setGroupFilterState] = useState("all");
  const [agentFilter, setAgentFilter] = useState("all");
  const { agents: allAgents, agentNameMap: allAgentNameMap } = useAgentsList();

  const { data: groups = [] } = useQuery<UserGroup[]>({
    queryKey: ["user-groups"],
    queryFn: getAllUserGroups,
    enabled: isAdmin,
  });

  const { data: groupAgents } = useQuery({
    queryKey: ["analytics-group-agents", groupFilter],
    queryFn: () => fetchGroupAgents(groupFilter),
    enabled: isAdmin && groupFilter !== "all",
  });

  const agents = useMemo(() => {
    if (!isAdmin || groupFilter === "all") return allAgents;
    return groupAgents ?? [];
  }, [isAdmin, groupFilter, allAgents, groupAgents]);

  const agentNameMap = useMemo(() => {
    const map = { ...allAgentNameMap };
    for (const a of groupAgents ?? []) {
      map[a.id] = a.name;
    }
    return map;
  }, [allAgentNameMap, groupAgents]);

  const setGroupFilter = useCallback((value: string) => {
    setGroupFilterState(value);
    setAgentFilter("all");
  }, []);

  const filterParams: Pick<AnalyticsFilterParams, "agent_id" | "group_id"> = useMemo(
    () => ({
      agent_id: agentFilter !== "all" ? agentFilter : undefined,
      group_id:
        isAdmin && groupFilter !== "all" && agentFilter === "all"
          ? groupFilter
          : undefined,
    }),
    [agentFilter, groupFilter, isAdmin],
  );

  const showGroupFilter = isAdmin && groups.length > 0;

  return {
    groups,
    showGroupFilter,
    groupFilter,
    setGroupFilter,
    agentFilter,
    setAgentFilter,
    agents,
    agentNameMap,
    filterParams,
  };
}
