import { apiRequest } from "@/config/api";
import type {
  AgentDailyStatsListResponse,
  AgentStatsSummaryResponse,
  NodeDailyStatsListResponse,
  NodeTypeBreakdownResponse,
  AnalyticsFilterParams,
} from "@/interfaces/analyticsReports.interface";

function buildQueryString(params: Record<string, string | undefined>): string {
  const parts = Object.entries(params)
    .filter(([, v]) => v !== undefined && v !== "")
    .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v as string)}`);
  return parts.length > 0 ? `?${parts.join("&")}` : "";
}

export const fetchAgentDailyStats = async (
  params?: Pick<AnalyticsFilterParams, "agent_id" | "from_date" | "to_date">
): Promise<AgentDailyStatsListResponse | null> => {
  try {
    const qs = buildQueryString({
      agent_id: params?.agent_id,
      from_date: params?.from_date,
      to_date: params?.to_date,
    });
    return await apiRequest<AgentDailyStatsListResponse>("get", `/analytics/agents${qs}`);
  } catch (error) {
    console.error("Error fetching agent daily stats:", error);
    return null;
  }
};

export const fetchAgentStatsSummary = async (
  params?: Pick<AnalyticsFilterParams, "agent_id" | "from_date" | "to_date">
): Promise<AgentStatsSummaryResponse | null> => {
  try {
    const qs = buildQueryString({
      agent_id: params?.agent_id,
      from_date: params?.from_date,
      to_date: params?.to_date,
    });
    return await apiRequest<AgentStatsSummaryResponse>("get", `/analytics/agents/summary${qs}`);
  } catch (error) {
    console.error("Error fetching agent stats summary:", error);
    return null;
  }
};

export const fetchNodeDailyStats = async (
  params?: AnalyticsFilterParams
): Promise<NodeDailyStatsListResponse | null> => {
  try {
    const qs = buildQueryString({
      agent_id: params?.agent_id,
      node_type: params?.node_type,
      from_date: params?.from_date,
      to_date: params?.to_date,
    });
    return await apiRequest<NodeDailyStatsListResponse>("get", `/analytics/nodes${qs}`);
  } catch (error) {
    console.error("Error fetching node daily stats:", error);
    return null;
  }
};

export const fetchAgentNodeBreakdown = async (
  agentId: string,
  params?: Pick<AnalyticsFilterParams, "from_date" | "to_date">
): Promise<NodeTypeBreakdownResponse | null> => {
  try {
    const qs = buildQueryString({
      from_date: params?.from_date,
      to_date: params?.to_date,
    });
    return await apiRequest<NodeTypeBreakdownResponse>(
      "get",
      `/analytics/agents/${agentId}/nodes/breakdown${qs}`
    );
  } catch (error) {
    console.error("Error fetching agent node breakdown:", error);
    return null;
  }
};
