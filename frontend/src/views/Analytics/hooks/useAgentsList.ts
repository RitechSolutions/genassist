import { useState, useEffect, useMemo } from "react";
import { getAgentConfigsList } from "@/services/api";
import type { AgentListItem } from "@/interfaces/ai-agent.interface";

export const useAgentsList = () => {
  const [agents, setAgents] = useState<AgentListItem[]>([]);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    getAgentConfigsList(1, 100)
      .then((r) => {
        // Response is null on 403. Leaving loaded false stops callers treating a failed
        // fetch as proof an agent is gone
        if (!Array.isArray(r?.items)) return;
        setAgents(r.items);
        setLoaded(true);
      })
      .catch(() => {});
  }, []);

  const agentNameMap = useMemo(
    () => Object.fromEntries(agents.map((a) => [a.id, a.name])),
    [agents],
  );

  return { agents, agentNameMap, loaded };
};
