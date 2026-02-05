import { apiRequest } from "@/config/api";
import type {
  DashboardResponse,
  DashboardSummaryStats,
  ActiveConversationsResponse,
  AgentStatsResponse,
  IntegrationsResponse,
} from "@/interfaces/dashboard.interface";

/**
 * Fetch complete dashboard data
 */
export const fetchDashboard = async (
  days: number = 30,
  conversationsPage: number = 1,
  conversationsPageSize: number = 3
): Promise<DashboardResponse | null> => {
  try {
    return await apiRequest<DashboardResponse>(
      "get",
      `/dashboard?days=${days}&conversations_page=${conversationsPage}&conversations_page_size=${conversationsPageSize}`
    );
  } catch (error) {
    console.error("Error fetching dashboard:", error);
    return null;
  }
};

/**
 * Fetch dashboard summary statistics
 */
export const fetchDashboardSummary = async (
  days: number = 30
): Promise<DashboardSummaryStats | null> => {
  try {
    return await apiRequest<DashboardSummaryStats>(
      "get",
      `/dashboard/summary?days=${days}`
    );
  } catch (error) {
    console.error("Error fetching dashboard summary:", error);
    return null;
  }
};

/**
 * Fetch active conversations for dashboard with pagination
 */
export const fetchDashboardConversations = async (
  days: number = 30,
  page: number = 1,
  pageSize: number = 10
): Promise<ActiveConversationsResponse | null> => {
  try {
    return await apiRequest<ActiveConversationsResponse>(
      "get",
      `/dashboard/conversations?days=${days}&page=${page}&page_size=${pageSize}`
    );
  } catch (error) {
    console.error("Error fetching dashboard conversations:", error);
    return null;
  }
};

/**
 * Fetch agent statistics for dashboard
 */
export const fetchDashboardAgents = async (
  days: number = 30
): Promise<AgentStatsResponse | null> => {
  try {
    return await apiRequest<AgentStatsResponse>(
      "get",
      `/dashboard/agents?days=${days}`
    );
  } catch (error) {
    console.error("Error fetching dashboard agents:", error);
    return null;
  }
};

/**
 * Fetch integrations for dashboard
 */
export const fetchDashboardIntegrations = async (): Promise<IntegrationsResponse | null> => {
  try {
    return await apiRequest<IntegrationsResponse>(
      "get",
      `/dashboard/integrations`
    );
  } catch (error) {
    console.error("Error fetching dashboard integrations:", error);
    return null;
  }
};

/**
 * Convert days filter value to number of days
 */
export const getFilterDays = (timeFilter: string): number => {
  switch (timeFilter) {
    case "today":
      return 1;
    case "7days":
      return 7;
    case "30days":
      return 30;
    case "6months":
      return 180;
    case "12months":
      return 365;
    default:
      return 30;
  }
};
