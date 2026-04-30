import { Bell } from "lucide-react"

import { Card } from "@/components/card"
import { PageLayout } from "@/components/PageLayout"
import { Switch } from "@/components/switch"
import { useNotificationPreferences } from "@/hooks/useNotificationPreferences"

export function NotificationsSettings() {
  const { preferences, setPreference } = useNotificationPreferences()

  return (
    <PageLayout>
      <header className="mb-8">
        <h1 className="text-2xl sm:text-3xl font-bold mb-2">Notifications</h1>
        <p className="text-sm sm:text-base text-muted-foreground">
          Customize which notifications you want to receive.
        </p>
      </header>

      <Card className="overflow-hidden rounded-lg border bg-white shadow-sm">
        <div className="px-6 py-4">
          <h3 className="text-base font-semibold text-zinc-900">
            Notification Preferences
          </h3>
          <p className="text-sm text-zinc-500">
            Enable or disable specific notification types for your account.
          </p>
        </div>

        <div className="px-6 py-3">
          <div className="flex items-center justify-between gap-4 px-2 py-2">
            <div className="flex items-start gap-3">
              <Bell className="mt-0.5 h-4 w-4 text-blue-600" />
              <div>
                <p className="text-sm font-medium text-zinc-900">
                  Conversation Started
                </p>
                <p className="text-xs text-zinc-500">
                  Get notified when a new conversation is started.
                </p>
              </div>
            </div>
            <Switch
              checked={preferences.conversationStarted}
              onCheckedChange={(value) =>
                setPreference("conversationStarted", value)
              }
              aria-label="Toggle conversation started notifications"
            />
          </div>
        </div>
      </Card>
    </PageLayout>
  )
}
