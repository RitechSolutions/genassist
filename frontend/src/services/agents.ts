import { apiRequest } from "@/config/api";
import { Agent } from "@/interfaces/agent.interface";

export const fetchAgents = async (): Promise<Agent[]> => {
  const response = await apiRequest<Agent[]>("get", "/operators/");
  return response && Array.isArray(response) ? response : [];
};

export const fetchAgentById = async (
  agentId: string
): Promise<Agent | null> => {
  const response = await apiRequest<Agent>("get", `/operator/${agentId}`);
  return response ?? null;
};
