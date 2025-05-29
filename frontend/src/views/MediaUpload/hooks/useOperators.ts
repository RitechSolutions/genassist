import { useState, useEffect } from 'react';
import { fetchOperators } from '@/services/operators';
import { Operator as BaseOperator } from '@/interfaces/operator.interface';

export interface Operator extends BaseOperator{
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

export const useOperators = () => {
  const [operators, setOperators] = useState<Operator[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const [imageErrors, setImageErrors] = useState<Set<string>>(new Set());

  useEffect(() => {
    const getOperators = async () => {
      try {
        setLoading(true);
        const data = await fetchOperators();
        const mappedAgents: Operator[] = data.map((agent: MappedAgent) => ({
          id: agent.id || agent._id || `agent-${Math.random().toString(36).substr(2, 9)}`,
          firstName: agent.firstName || agent.first_name || 'Unknown',
          lastName: agent.lastName || agent.last_name || 'Operator',
          avatar: agent.avatar || agent.profile_image || null
        }));
        setOperators(mappedAgents);
        setError(null);
      } catch (err) {
        console.error("Error fetching agents:", err);
        setError(err instanceof Error ? err : new Error("Failed to fetch agents"));
        setOperators([]);
      } finally {
        setLoading(false);
      }
    };

    getOperators();
  }, []);

  return {
    operators,
    loading,
    error,
    imageErrors,
    setImageErrors
  };
}; 