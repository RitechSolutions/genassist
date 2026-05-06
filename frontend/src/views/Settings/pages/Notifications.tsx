import { Bell, TriangleAlert, ShieldAlert, Workflow } from "lucide-react"

import { Card } from "@/components/card"
import { PageLayout } from "@/components/PageLayout"
import { Switch } from "@/components/switch"
import { useNotificationPreferences } from "@/hooks/useNotificationPreferences"

export function NotificationsSettings() {
  const { preferences, setPreference, isLoading, isSaving } =
    useNotificationPreferences()

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
            Enable or disable notification types based on your access level.
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
              disabled={isLoading || isSaving}
              aria-label="Toggle conversation started notifications"
            />
          </div>
          <div className="flex items-center justify-between gap-4 px-2 py-2">
            <div className="flex items-start gap-3">
              <TriangleAlert className="mt-0.5 h-4 w-4 text-amber-600" />
              <div>
                <p className="text-sm font-medium text-zinc-900">
                  High Hostility Detected
                </p>
                <p className="text-xs text-zinc-500">
                  Get notified when a live conversation reaches high hostility.
                </p>
              </div>
            </div>
            <Switch
              checked={preferences.conversationHostility}
              onCheckedChange={(value) =>
                setPreference("conversationHostility", value)
              }
              disabled={isLoading || isSaving}
              aria-label="Toggle high hostility notifications"
            />
          </div>
          <div className="flex items-center justify-between gap-4 px-2 py-2">
            <div className="flex items-start gap-3">
              <ShieldAlert className="mt-0.5 h-4 w-4 text-amber-700" />
              <div>
                <p className="text-sm font-medium text-zinc-900">
                  Live Conversation Finalized
                </p>
                <p className="text-xs text-zinc-500">
                  Get notified when a high-hostility conversation is finalized.
                </p>
              </div>
            </div>
            <Switch
              checked={preferences.conversationFinalizedHostility}
              onCheckedChange={(value) =>
                setPreference("conversationFinalizedHostility", value)
              }
              disabled={isLoading || isSaving}
              aria-label="Toggle finalized hostility notifications"
            />
          </div>
          {preferences.canManageWorkflowFailed ? (
            <div className="flex items-center justify-between gap-4 px-2 py-2">
              <div className="flex items-start gap-3">
                <Workflow className="mt-0.5 h-4 w-4 text-red-600" />
                <div>
                  <p className="text-sm font-medium text-zinc-900">
                    Workflow Run Failed
                  </p>
                  <p className="text-xs text-zinc-500">
                    Tenant-level setting for failed pipeline and test runs.
                  </p>
                </div>
              </div>
              <Switch
                checked={preferences.workflowFailed}
                onCheckedChange={(value) => setPreference("workflowFailed", value)}
                disabled={isLoading || isSaving}
                aria-label="Toggle workflow failed notifications"
              />
            </div>
          ) : null}
        </div>
      </Card>
    </PageLayout>
  )
}
