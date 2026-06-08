import { apiRequest } from "@/config/api"

export type NotificationUserSettings = {
  conversationStarted: boolean
  conversationHostility: boolean
  conversationFinalizedHostility: boolean
  workflowFailed: boolean
  canManageWorkflowFailed: boolean
}

type NotificationUserSettingsRaw = {
  conversation_started: boolean
  conversation_hostility: boolean
  conversation_finalized_hostility: boolean
  workflow_failed: boolean
  can_manage_workflow_failed: boolean
}

export type NotificationUserSettingsUpdate = Partial<
  Pick<
    NotificationUserSettings,
    | "conversationStarted"
    | "conversationHostility"
    | "conversationFinalizedHostility"
    | "workflowFailed"
  >
>

function mapUserSettings(raw: NotificationUserSettingsRaw): NotificationUserSettings {
  return {
    conversationStarted: raw.conversation_started,
    conversationHostility: raw.conversation_hostility,
    conversationFinalizedHostility: raw.conversation_finalized_hostility,
    workflowFailed: raw.workflow_failed,
    canManageWorkflowFailed: raw.can_manage_workflow_failed,
  }
}

function mapUserSettingsUpdates(
  updates: NotificationUserSettingsUpdate
): Record<string, boolean> {
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

export async function fetchNotificationUserSettings(): Promise<NotificationUserSettings | null> {
  try {
    const response = await apiRequest<NotificationUserSettingsRaw>(
      "get",
      "/notifications"
    )
    if (!response) return null
    return mapUserSettings(response)
  } catch (error) {
    console.error("Error fetching notification user settings:", error)
    return null
  }
}

export async function updateNotificationUserSettings(
  updates: NotificationUserSettingsUpdate
): Promise<NotificationUserSettings | null> {
  try {
    const payload = mapUserSettingsUpdates(updates)
    if (Object.keys(payload).length === 0) return null
    const response = await apiRequest<NotificationUserSettingsRaw>(
      "patch",
      "/notifications",
      payload
    )
    if (!response) return null
    return mapUserSettings(response)
  } catch (error) {
    console.error("Error updating notification user settings:", error)
    return null
  }
}
