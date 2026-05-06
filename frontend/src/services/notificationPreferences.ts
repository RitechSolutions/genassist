import { apiRequest } from "@/config/api"

export type NotificationPreferences = {
  conversationStarted: boolean
  conversationHostility: boolean
  conversationFinalizedHostility: boolean
  workflowFailed: boolean
  canManageWorkflowFailed: boolean
}

type NotificationPreferencesRaw = {
  conversation_started: boolean
  conversation_hostility: boolean
  conversation_finalized_hostility: boolean
  workflow_failed: boolean
  can_manage_workflow_failed: boolean
}

export type NotificationPreferencesUpdate = Partial<
  Pick<
    NotificationPreferences,
    | "conversationStarted"
    | "conversationHostility"
    | "conversationFinalizedHostility"
    | "workflowFailed"
  >
>

function mapPreferences(raw: NotificationPreferencesRaw): NotificationPreferences {
  return {
    conversationStarted: raw.conversation_started,
    conversationHostility: raw.conversation_hostility,
    conversationFinalizedHostility: raw.conversation_finalized_hostility,
    workflowFailed: raw.workflow_failed,
    canManageWorkflowFailed: raw.can_manage_workflow_failed,
  }
}

function mapUpdates(updates: NotificationPreferencesUpdate): Record<string, boolean> {
  const payload: Record<string, boolean> = {}
  if (typeof updates.conversationStarted === "boolean") {
    payload.conversation_started = updates.conversationStarted
  }
  if (typeof updates.conversationHostility === "boolean") {
    payload.conversation_hostility = updates.conversationHostility
  }
  if (typeof updates.conversationFinalizedHostility === "boolean") {
    payload.conversation_finalized_hostility = updates.conversationFinalizedHostility
  }
  if (typeof updates.workflowFailed === "boolean") {
    payload.workflow_failed = updates.workflowFailed
  }
  return payload
}

export async function fetchNotificationPreferences(): Promise<NotificationPreferences | null> {
  try {
    const response = await apiRequest<NotificationPreferencesRaw>(
      "get",
      "/notification-preferences"
    )
    if (!response) return null
    return mapPreferences(response)
  } catch (error) {
    console.error("Error fetching notification preferences:", error)
    return null
  }
}

export async function updateNotificationPreferences(
  updates: NotificationPreferencesUpdate
): Promise<NotificationPreferences | null> {
  try {
    const payload = mapUpdates(updates)
    if (Object.keys(payload).length === 0) return null
    const response = await apiRequest<NotificationPreferencesRaw>(
      "patch",
      "/notification-preferences",
      payload
    )
    if (!response) return null
    return mapPreferences(response)
  } catch (error) {
    console.error("Error updating notification preferences:", error)
    return null
  }
}
