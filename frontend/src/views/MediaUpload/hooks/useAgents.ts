import { useState, useEffect } from 'react';
import { fetchAgents } from '@/services/agents';
import { Agent as BaseAgent } from '@/interfaces/agent.interface';

export interface Agent extends BaseAgent {
  id: string;
}

interface MappedAgent {
  id?: string;
  _id?: string;
  firstName?: string;
  first_name?: string;
  lastName?: string;
  last_name?: string;
  avatar?: string | null;
  profile_image?: string | null;
  [key: string]: string | number | boolean | object | null | undefined;
}

export const useAgents = () => {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const [imageErrors, setImageErrors] = useState<Set<string>>(new Set());

  useEffect(() => {
    const getAgents = async () => {
      try {
        setLoading(true);
        const data = await fetchAgents();
        const mappedAgents: Agent[] = data.map((agent: MappedAgent) => ({
          id: agent.id || agent._id || `agent-${Math.random().toString(36).substr(2, 9)}`,
          firstName: agent.firstName || agent.first_name || 'Unknown',
          lastName: agent.lastName || agent.last_name || 'Operator',
          avatar: agent.avatar || agent.profile_image || null
        }));
        setAgents(mappedAgents);
        setError(null);
      } catch (err) {
        console.error("Error fetching agents:", err);
        setError(err instanceof Error ? err : new Error("Failed to fetch agents"));
        setAgents([]);
      } finally {
        setLoading(false);
      }
    };

    getAgents();
  }, []);

  return {
    agents,
    loading,
    error,
    imageErrors,
    setImageErrors
  };
}; 