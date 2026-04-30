import { useCallback, useEffect, useState } from "react"

export const NOTIFICATION_PREFERENCES_STORAGE_KEY = "notification_preferences"
export const CONVERSATION_STARTED_PREF_KEY = "conversationStarted"

export type NotificationPreferences = {
  conversationStarted: boolean
}

const DEFAULT_NOTIFICATION_PREFERENCES: NotificationPreferences = {
  conversationStarted: true,
}

function readPreferences(): NotificationPreferences {
  try {
    const raw = localStorage.getItem(NOTIFICATION_PREFERENCES_STORAGE_KEY)
    if (!raw) return DEFAULT_NOTIFICATION_PREFERENCES
    return {
      ...DEFAULT_NOTIFICATION_PREFERENCES,
      ...(JSON.parse(raw) as Partial<NotificationPreferences>),
    }
  } catch {
    return DEFAULT_NOTIFICATION_PREFERENCES
  }
}

function writePreferences(preferences: NotificationPreferences): void {
  localStorage.setItem(
    NOTIFICATION_PREFERENCES_STORAGE_KEY,
    JSON.stringify(preferences)
  )
}

export function isConversationStartedNotification(notificationId: string): boolean {
  return notificationId.startsWith("conversation_started:")
}

export function useNotificationPreferences() {
  const [preferences, setPreferences] = useState<NotificationPreferences>(
    DEFAULT_NOTIFICATION_PREFERENCES
  )

  useEffect(() => {
    setPreferences(readPreferences())
  }, [])

  const setPreference = useCallback(
    (key: keyof NotificationPreferences, value: boolean) => {
      setPreferences((prev) => {
        const next = { ...prev, [key]: value }
        writePreferences(next)
        return next
      })
    },
    []
  )

  return {
    preferences,
    setPreference,
  }
}
