import { useCallback, useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { currentUserIsAdmin } from "@/services/auth";
import { getAllUserGroups } from "@/services/userGroups";
import { fetchGroupAgents } from "@/services/analyticsReports";
import type { AnalyticsFilterParams } from "@/interfaces/analyticsReports.interface";
import type { UserGroup } from "@/interfaces/userGroup.interface";
import { useAgentsList } from "./useAgentsList";

export function useAnalyticsFilters() {
  const isAdmin = currentUserIsAdmin();
  const [selectedGroup, setSelectedGroup] = useState("all");
  const [selectedAgent, setSelectedAgent] = useState("all");
  const {
    agents: allAgents,
    agentNameMap: allAgentNameMap,
    loaded: allAgentsLoaded,
  } = useAgentsList();

  const { data: groupsData } = useQuery<UserGroup[]>({
    queryKey: ["user-groups"],
    queryFn: getAllUserGroups,
    enabled: isAdmin,
  });
  const groupsLoaded = Array.isArray(groupsData);
  const groups = groupsLoaded ? groupsData : [];
  const groupExists = groups.some((g) => g.id === selectedGroup);
  const groupFilter = isAdmin && groupExists ? selectedGroup : "all";
  const groupWasDeleted = selectedGroup !== "all" && groupsLoaded && !groupExists;
  useEffect(() => {
    if (groupWasDeleted) setSelectedGroup("all");
  }, [groupWasDeleted]);

  const { data: groupAgents } = useQuery({
    queryKey: ["analytics-group-agents", groupFilter],
    queryFn: () => fetchGroupAgents(groupFilter),
    enabled: isAdmin && groupFilter !== "all",
  });

  const agents = useMemo(() => {
    if (!isAdmin || groupFilter === "all") return allAgents;
    return groupAgents ?? [];
  }, [isAdmin, groupFilter, allAgents, groupAgents]);

  const agentsLoaded =
    isAdmin && groupFilter !== "all" ? groupAgents !== undefined : allAgentsLoaded;
  const agentExists = agents.some((a) => a.id === selectedAgent);
  const agentFilter = agentExists ? selectedAgent : "all";

  const agentWasDeleted = selectedAgent !== "all" && agentsLoaded && !agentExists;
  useEffect(() => {
    if (agentWasDeleted) setSelectedAgent("all");
  }, [agentWasDeleted]);

  const agentNameMap = useMemo(() => {
    const map = { ...allAgentNameMap };
    for (const a of groupAgents ?? []) {
      map[a.id] = a.name;
    }
    return map;
  }, [allAgentNameMap, groupAgents]);

  const setGroupFilter = useCallback((value: string) => {
    setSelectedGroup(value);
    setSelectedAgent("all");
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
    setAgentFilter: setSelectedAgent,
    agents,
    agentNameMap,
    filterParams,
  };
}
