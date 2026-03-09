import { useState, useEffect, useMemo } from "react";
import { getAgentConfigsList } from "@/services/api";
import type { AgentListItem } from "@/interfaces/ai-agent.interface";

export const useAgentsList = () => {
  const [agents, setAgents] = useState<AgentListItem[]>([]);

  useEffect(() => {
    getAgentConfigsList(1, 100)
      .then((r) => setAgents(r.items))
      .catch(() => {});
  }, []);

  const agentNameMap = useMemo(
    () => Object.fromEntries(agents.map((a) => [a.id, a.name])),
    [agents],
  );

  return { agents, agentNameMap };
};
