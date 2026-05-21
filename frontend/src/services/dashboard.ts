import { apiRequest } from "@/config/api";
import type {
  DashboardResponse,
  DashboardSummaryStats,
  ActiveConversationsResponse,
  AgentStatsResponse,
  IntegrationsResponse,
} from "@/interfaces/dashboard.interface";
import type { Notification } from "@/interfaces/notification.interface";

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

type NotificationFeedItemRaw = Omit<Notification, "actionUrl"> & {
  action_url: string;
};

function mapNotificationFeedItems(
  items: NotificationFeedItemRaw[]
): Notification[] {
  return items.map((item) => ({
    id: item.id,
    title: item.title,
    description: item.description,
    timestamp: item.timestamp,
    type: item.type,
    read: Boolean(item.read),
    actionUrl: item.action_url,
  }));
}

export type NotificationFeedPageResult = {
  items: Notification[];
  hasMore: boolean;
};

export type NotificationBellPreview = {
  items: Notification[];
  unreadCount: number;
};

export const NOTIFICATIONS_PAGE_SIZE = 20;

export type NotificationTypeFilter =
  | "all"
  | "conversation_started"
  | "conversation_hostility"
  | "conversation_finalized_hostility";

type NotificationFeedIncludeOptions = {
  includeConversationStarted: boolean;
  includeConversationHostility: boolean;
  includeConversationFinalizedHostility: boolean;
  includeWorkflowFailed: boolean;
};

function appendNotificationFeedIncludes(
  params: URLSearchParams,
  includes: NotificationFeedIncludeOptions
): void {
  params.set(
    "include_conversation_started",
    String(includes.includeConversationStarted)
  );
  params.set(
    "include_conversation_hostility",
    String(includes.includeConversationHostility)
  );
  params.set(
    "include_conversation_finalized_hostility",
    String(includes.includeConversationFinalizedHostility)
  );
  params.set("include_workflow_failed", String(includes.includeWorkflowFailed));
}

/** Paginated notification feed (merged, sorted server-side). */
export const fetchDashboardNotificationsPage = async (
  limit: number,
  skip: number,
  includes: NotificationFeedIncludeOptions,
  notificationType: NotificationTypeFilter = "all",
  unreadOnly = false
): Promise<NotificationFeedPageResult | null> => {
  try {
    const params = new URLSearchParams();
    params.set("limit", String(limit));
    params.set("skip", String(skip));
    params.set("notification_type", notificationType);
    params.set("unread_only", String(unreadOnly));
    appendNotificationFeedIncludes(params, includes);
    const response = await apiRequest<{
      items: NotificationFeedItemRaw[];
      has_more: boolean;
    }>("get", `/dashboard/notifications?${params.toString()}`);
    if (!response) return null;
    return {
      items: mapNotificationFeedItems(response.items),
      hasMore: Boolean(response.has_more),
    };
  } catch (error) {
    console.error("Error fetching dashboard notifications:", error);
    return null;
  }
};

/** Latest notifications for the header bell (max 10) plus unread badge count. */
export const fetchNotificationBellPreview = async (
  includes: NotificationFeedIncludeOptions
): Promise<NotificationBellPreview | null> => {
  try {
    const params = new URLSearchParams();
    appendNotificationFeedIncludes(params, includes);
    const response = await apiRequest<{
      items: NotificationFeedItemRaw[];
      unread_count: number;
    }>("get", `/dashboard/notifications/bell?${params.toString()}`);
    if (!response) return null;
    return {
      items: mapNotificationFeedItems(response.items),
      unreadCount: response.unread_count ?? 0,
    };
  } catch (error) {
    console.error("Error fetching notification bell preview:", error);
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
