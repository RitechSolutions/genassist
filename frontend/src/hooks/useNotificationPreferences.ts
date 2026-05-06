import { useCallback } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import {
  fetchNotificationPreferences,
  updateNotificationPreferences,
  type NotificationPreferences,
  type NotificationPreferencesUpdate,
} from "@/services/notificationPreferences"

export const CONVERSATION_STARTED_PREF_KEY = "conversationStarted"
export const CONVERSATION_HOSTILITY_PREF_KEY = "conversationHostility"
export const CONVERSATION_FINALIZED_HOSTILITY_PREF_KEY =
  "conversationFinalizedHostility"
export const WORKFLOW_FAILED_PREF_KEY = "workflowFailed"

const DEFAULT_NOTIFICATION_PREFERENCES: NotificationPreferences = {
  conversationStarted: true,
  conversationHostility: true,
  conversationFinalizedHostility: true,
  workflowFailed: true,
  canManageWorkflowFailed: false,
}

export const NOTIFICATION_PREFERENCES_QUERY_KEY = [
  "notification-preferences",
] as const

export function isConversationStartedNotification(notificationId: string): boolean {
  return notificationId.startsWith("conversation_started:")
}

export function isConversationHostilityNotification(notificationId: string): boolean {
  return notificationId.startsWith("conversation_hostility:")
}

export function isConversationFinalizedHostilityNotification(
  notificationId: string
): boolean {
  return notificationId.startsWith("conversation_finalized_hostility:")
}

export function isWorkflowFailedNotification(notificationId: string): boolean {
  return notificationId.startsWith("workflow_failed:")
}

export function useNotificationPreferences() {
  const queryClient = useQueryClient()
  const { data, isLoading } = useQuery<NotificationPreferences>({
    queryKey: NOTIFICATION_PREFERENCES_QUERY_KEY,
    queryFn: async () => {
      const response = await fetchNotificationPreferences()
      return response ?? DEFAULT_NOTIFICATION_PREFERENCES
    },
  })

  const preferences = data ?? DEFAULT_NOTIFICATION_PREFERENCES
  const mutation = useMutation({
    mutationFn: async (updates: NotificationPreferencesUpdate) => {
      const response = await updateNotificationPreferences(updates)
      return response ?? preferences
    },
    onSuccess: (next) => {
      queryClient.setQueryData(NOTIFICATION_PREFERENCES_QUERY_KEY, next)
    },
  })

  const setPreference = useCallback(
    (
      key: Exclude<keyof NotificationPreferences, "canManageWorkflowFailed">,
      value: boolean
    ) => {
      const updates: NotificationPreferencesUpdate = { [key]: value }
      void mutation.mutateAsync(updates)
    },
    [mutation]
  )

  return {
    preferences,
    setPreference,
    isLoading,
    isSaving: mutation.isPending,
  }
}
