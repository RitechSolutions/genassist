import { useMemo, useState } from "react"
import { Bell, Settings2, ShieldAlert, TriangleAlert, Workflow } from "lucide-react"

import { Button } from "@/components/button"
import { Card } from "@/components/card"
import { PageLayout } from "@/components/PageLayout"
import { Switch } from "@/components/switch"
import { useNotificationAdminTargeting } from "@/hooks/useNotificationAdminTargeting"
import { useNotificationUserSettings } from "@/hooks/useNotificationUserSettings"
import { currentUserIsAdmin } from "@/services/auth"
import type { NotificationTypeTargeting } from "@/services/notificationAdminTargeting"
import {
  NotificationAudienceDialog,
  type NotificationAudienceTypeKey,
} from "@/views/Settings/components/NotificationAudienceDialog"

export function NotificationsSettings() {
  const { settings, setSetting, isLoading, isSaving } =
    useNotificationUserSettings()
  const isAdmin = currentUserIsAdmin()
  const [audienceTypeKey, setAudienceTypeKey] =
    useState<NotificationAudienceTypeKey | null>(null)

  const {
    data: adminBundle,
    isLoading: adminTargetingLoading,
    saveTargeting,
    isSaving: audienceSaving,
    savingTypeKey,
  } = useNotificationAdminTargeting(isAdmin)

  const targetingByKey = useMemo(() => {
    const m = new Map<string, NotificationTypeTargeting>()
    if (!adminBundle?.targeting) return m
    for (const t of adminBundle.targeting) {
      m.set(t.typeKey, t)
    }
    return m
  }, [adminBundle?.targeting])

  const audienceTargetingRow = audienceTypeKey
    ? targetingByKey.get(audienceTypeKey)
    : undefined

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
            Notification types
          </h3>
          <p className="text-sm text-zinc-500">
            Enable or disable notification types based on your access level.
            {isAdmin ? (
              <>
                {" "}
                Use the settings icon to control which users or groups receive each type
                tenant-wide.
              </>
            ) : null}
          </p>
        </div>

        <div className="px-6 py-3">
          <div className="flex items-center justify-between gap-4 px-2 py-2">
            <div className="flex items-start gap-3 min-w-0 flex-1">
              <Bell className="mt-0.5 h-4 w-4 shrink-0 text-blue-600" />
              <div className="min-w-0">
                <p className="text-sm font-medium text-zinc-900">
                  Conversation Started
                </p>
                <p className="text-xs text-zinc-500">
                  Get notified when a new conversation is started.
                </p>
              </div>
            </div>
            <div className="flex shrink-0 items-center gap-1">
              <Switch
                checked={settings.conversationStarted}
                onCheckedChange={(value) =>
                  setSetting("conversationStarted", value)
                }
                disabled={isLoading || isSaving}
                aria-label="Toggle conversation started notifications"
              />
              {isAdmin ? (
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="h-9 w-9 rounded-full text-zinc-600"
                  title="Who receives this notification"
                  disabled={adminTargetingLoading}
                  onClick={() => setAudienceTypeKey("conversation_started")}
                  aria-label="Configure audience for conversation started"
                >
                  <Settings2 className="h-4 w-4" />
                </Button>
              ) : null}
            </div>
          </div>
          <div className="flex items-center justify-between gap-4 px-2 py-2">
            <div className="flex items-start gap-3 min-w-0 flex-1">
              <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0 text-amber-600" />
              <div className="min-w-0">
                <p className="text-sm font-medium text-zinc-900">
                  High Hostility Detected
                </p>
                <p className="text-xs text-zinc-500">
                  Get notified when a live conversation reaches high hostility.
                </p>
              </div>
            </div>
            <div className="flex shrink-0 items-center gap-1">
              <Switch
                checked={settings.conversationHostility}
                onCheckedChange={(value) =>
                  setSetting("conversationHostility", value)
                }
                disabled={isLoading || isSaving}
                aria-label="Toggle high hostility notifications"
              />
              {isAdmin ? (
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="h-9 w-9 rounded-full text-zinc-600"
                  title="Who receives this notification"
                  disabled={adminTargetingLoading}
                  onClick={() => setAudienceTypeKey("conversation_hostility")}
                  aria-label="Configure audience for high hostility"
                >
                  <Settings2 className="h-4 w-4" />
                </Button>
              ) : null}
            </div>
          </div>
          <div className="flex items-center justify-between gap-4 px-2 py-2">
            <div className="flex items-start gap-3 min-w-0 flex-1">
              <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0 text-amber-700" />
              <div className="min-w-0">
                <p className="text-sm font-medium text-zinc-900">
                  Live Conversation Finalized
                </p>
                <p className="text-xs text-zinc-500">
                  Get notified when a high-hostility conversation is finalized.
                </p>
              </div>
            </div>
            <div className="flex shrink-0 items-center gap-1">
              <Switch
                checked={settings.conversationFinalizedHostility}
                onCheckedChange={(value) =>
                  setSetting("conversationFinalizedHostility", value)
                }
                disabled={isLoading || isSaving}
                aria-label="Toggle finalized hostility notifications"
              />
              {isAdmin ? (
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="h-9 w-9 rounded-full text-zinc-600"
                  title="Who receives this notification"
                  disabled={adminTargetingLoading}
                  onClick={() =>
                    setAudienceTypeKey("conversation_finalized_hostility")
                  }
                  aria-label="Configure audience for finalized hostility"
                >
                  <Settings2 className="h-4 w-4" />
                </Button>
              ) : null}
            </div>
          </div>
          {settings.canManageWorkflowFailed ? (
            <div className="flex items-center justify-between gap-4 px-2 py-2">
              <div className="flex items-start gap-3 min-w-0 flex-1">
                <Workflow className="mt-0.5 h-4 w-4 shrink-0 text-red-600" />
                <div className="min-w-0">
                  <p className="text-sm font-medium text-zinc-900">
                    Workflow Run Failed
                  </p>
                  <p className="text-xs text-zinc-500">
                    Tenant-level setting for failed pipeline and test runs.
                  </p>
                </div>
              </div>
              <div className="flex shrink-0 items-center gap-1">
                <Switch
                  checked={settings.workflowFailed}
                  onCheckedChange={(value) => setSetting("workflowFailed", value)}
                  disabled={isLoading || isSaving}
                  aria-label="Toggle workflow failed notifications"
                />
                {isAdmin ? (
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="h-9 w-9 rounded-full text-zinc-600"
                    title="Who receives this notification"
                    disabled={adminTargetingLoading}
                    onClick={() => setAudienceTypeKey("workflow_failed")}
                    aria-label="Configure audience for workflow failed"
                  >
                    <Settings2 className="h-4 w-4" />
                  </Button>
                ) : null}
              </div>
            </div>
          ) : null}
        </div>
      </Card>

      <NotificationAudienceDialog
        isOpen={audienceTypeKey !== null}
        onOpenChange={(open) => {
          if (!open) setAudienceTypeKey(null)
        }}
        typeKey={audienceTypeKey}
        targeting={audienceTargetingRow}
        users={adminBundle?.users ?? []}
        groups={adminBundle?.groups ?? []}
        onSave={async (typeKey, payload) => {
          await saveTargeting({ typeKey, payload })
        }}
        savingTypeKey={savingTypeKey}
        isSaving={audienceSaving}
      />
    </PageLayout>
  )
}
