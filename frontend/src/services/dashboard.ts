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

type NotificationFeedItemRaw = Omit<Notification, "read" | "actionUrl"> & {
  action_url: string;
  is_read?: boolean;
  notification_id?: string;
  type_key?: string;
  group_id?: string;
};

function mapNotificationFeedItems(
  items: NotificationFeedItemRaw[]
): Notification[] {
  return items.map((item) => ({
    id: item.id,
    notificationId: item.notification_id,
    typeKey: item.type_key,
    groupId: item.group_id,
    title: item.title,
    description: item.description,
    timestamp: item.timestamp,
    type: item.type,
    read: Boolean(item.is_read),
    actionUrl: item.action_url,
  }));
}

export type NotificationFeedPageResult = {
  items: Notification[];
  hasMore: boolean;
};

export type NotificationTypeFilter =
  | "all"
  | "conversation_started"
  | "conversation_hostility"
  | "conversation_finalized_hostility"
  | "workflow_failed";

/** Paginated notification feed (merged, sorted server-side). */
export const fetchDashboardNotificationsPage = async (
  limit: number,
  skip: number,
  includeConversationStarted: boolean,
  includeConversationHostility: boolean,
  includeConversationFinalizedHostility: boolean,
  includeWorkflowFailed: boolean,
  notificationType: NotificationTypeFilter = "all",
  notificationLevel: "all" | "info" | "success" | "warning" | "error" = "all"
): Promise<NotificationFeedPageResult | null> => {
  try {
    const params = new URLSearchParams();
    params.set("limit", String(limit));
    params.set("skip", String(skip));
    params.set("notification_type", notificationType);
    params.set("include_conversation_started", String(includeConversationStarted));
    params.set("include_conversation_hostility", String(includeConversationHostility));
    params.set(
      "include_conversation_finalized_hostility",
      String(includeConversationFinalizedHostility)
    );
    params.set("include_workflow_failed", String(includeWorkflowFailed));
    params.set("notification_level", notificationLevel);
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

export type FetchDashboardNotificationsOptions = {
  skip?: number;
  includeConversationStarted?: boolean;
  includeConversationHostility?: boolean;
  includeConversationFinalizedHostility?: boolean;
  includeWorkflowFailed?: boolean;
  notificationType?: NotificationTypeFilter;
  notificationLevel?: "all" | "info" | "success" | "warning" | "error";
};

/** First page (or window) of notifications for sidebar / bell cache. */
export const fetchDashboardNotifications = async (
  limit: number = 50,
  options?: FetchDashboardNotificationsOptions
): Promise<Notification[] | null> => {
  const page = await fetchDashboardNotificationsPage(
    limit,
    options?.skip ?? 0,
    options?.includeConversationStarted ?? true,
    options?.includeConversationHostility ?? true,
    options?.includeConversationFinalizedHostility ?? true,
    options?.includeWorkflowFailed ?? true,
    options?.notificationType ?? "all",
    options?.notificationLevel ?? "all"
  );
  return page?.items ?? null;
};

export const markNotificationsRead = async (
  notificationIds: string[],
  isRead: boolean = true
): Promise<boolean> => {
  try {
    await apiRequest<{ updated_count: number }>("patch", "/notifications/state/read", {
      notification_ids: notificationIds,
      is_read: isRead,
    });
    return true;
  } catch (error) {
    console.error("Error updating notification read state:", error);
    return false;
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
