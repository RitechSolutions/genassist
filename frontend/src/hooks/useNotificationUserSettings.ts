import { useCallback } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import {
  fetchNotificationUserSettings,
  updateNotificationUserSettings,
  type NotificationUserSettings,
  type NotificationUserSettingsUpdate,
} from "@/services/notificationSettings"

export const DEFAULT_NOTIFICATION_USER_SETTINGS: NotificationUserSettings = {
  conversationStarted: true,
  conversationHostility: true,
  conversationFinalizedHostility: true,
  workflowFailed: true,
  canManageWorkflowFailed: false,
}

export const NOTIFICATION_USER_SETTINGS_QUERY_KEY = [
  "notification-user-settings",
] as const

export function useNotificationUserSettings() {
  const queryClient = useQueryClient()
  const { data, isLoading } = useQuery<NotificationUserSettings>({
    queryKey: NOTIFICATION_USER_SETTINGS_QUERY_KEY,
    queryFn: async () => {
      const response = await fetchNotificationUserSettings()
      return response ?? DEFAULT_NOTIFICATION_USER_SETTINGS
    },
  })

  const settings = data ?? DEFAULT_NOTIFICATION_USER_SETTINGS
  const mutation = useMutation({
    mutationFn: async (updates: NotificationUserSettingsUpdate) => {
      const response = await updateNotificationUserSettings(updates)
      return response ?? settings
    },
    onSuccess: (next) => {
      queryClient.setQueryData(NOTIFICATION_USER_SETTINGS_QUERY_KEY, next)
    },
  })

  const setSetting = useCallback(
    (
      key: Exclude<keyof NotificationUserSettings, "canManageWorkflowFailed">,
      value: boolean
    ) => {
      const updates: NotificationUserSettingsUpdate = { [key]: value }
      void mutation.mutateAsync(updates)
    },
    [mutation]
  )

  return {
    settings,
    setSetting,
    isLoading,
    isSaving: mutation.isPending,
  }
}
