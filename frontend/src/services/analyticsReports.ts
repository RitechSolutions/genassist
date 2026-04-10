import { apiRequest } from "@/config/api";
import type {
  AgentDailyStatsListResponse,
  AgentStatsSummaryResponse,
  AgentStatsSummaryWithComparison,
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

export const fetchAgentStatsSummaryWithComparison = async (
  params?: Pick<AnalyticsFilterParams, "agent_id" | "from_date" | "to_date">
): Promise<AgentStatsSummaryWithComparison | null> => {
  try {
    const qs = buildQueryString({
      agent_id: params?.agent_id,
      from_date: params?.from_date,
      to_date: params?.to_date,
      compare: "true",
    });
    return await apiRequest<AgentStatsSummaryWithComparison>("get", `/analytics/agents/summary${qs}`);
  } catch (error) {
    console.error("Error fetching agent stats summary with comparison:", error);
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

export interface CustomAttributeBreakdownItem {
  value: string;
  conversation_count: number;
  avg_satisfaction: number | null;
  avg_resolution_rate: number | null;
  avg_efficiency: number | null;
  avg_quality: number | null;
}

export const fetchCustomAttributeKeys = async (
  agentId?: string
): Promise<string[]> => {
  try {
    const qs = buildQueryString({ agent_id: agentId });
    return (await apiRequest<string[]>("get", `/analytics/custom-attributes/keys${qs}`)) ?? [];
  } catch (error) {
    console.error("Error fetching custom attribute keys:", error);
    return [];
  }
};

export const fetchCustomAttributeBreakdown = async (
  key: string,
  params?: Pick<AnalyticsFilterParams, "agent_id" | "from_date" | "to_date">
): Promise<CustomAttributeBreakdownItem[]> => {
  try {
    const qs = buildQueryString({
      key,
      agent_id: params?.agent_id,
      from_date: params?.from_date,
      to_date: params?.to_date,
    });
    return (await apiRequest<CustomAttributeBreakdownItem[]>(
      "get",
      `/analytics/custom-attributes/breakdown${qs}`
    )) ?? [];
  } catch (error) {
    console.error("Error fetching custom attribute breakdown:", error);
    return [];
  }
};
