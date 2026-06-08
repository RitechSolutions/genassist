import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import {
  fetchNotificationAdminTargeting,
  putNotificationAdminTargeting,
  type NotificationTypeTargeting,
  type NotificationTypeTargetingPayload,
} from "@/services/notificationAdminTargeting"
import { getAllUserGroups } from "@/services/userGroups"
import { getAllUsers } from "@/services/users"
import type { User } from "@/interfaces/user.interface"
import type { UserGroup } from "@/interfaces/userGroup.interface"

export const NOTIFICATION_ADMIN_TARGETING_QUERY_KEY = [
  "notification-admin-targeting",
] as const

export type NotificationAdminTargetingBundle = {
  targeting: NotificationTypeTargeting[]
  users: User[]
  groups: UserGroup[]
}

export function useNotificationAdminTargeting(enabled: boolean) {
  const queryClient = useQueryClient()

  const query = useQuery({
    queryKey: NOTIFICATION_ADMIN_TARGETING_QUERY_KEY,
    enabled,
    queryFn: async (): Promise<NotificationAdminTargetingBundle> => {
      const [targeting, users, groups] = await Promise.all([
        fetchNotificationAdminTargeting(),
        getAllUsers(),
        getAllUserGroups(),
      ])
      if (!targeting) {
        throw new Error("Failed to load notification audience settings")
      }
      return {
        targeting,
        users: users
          .filter((u) => u.is_active === 1 && u.is_deleted !== 1)
          .filter((u) => !u.roles?.some((r) => r.name === "admin")),
        groups,
      }
    },
  })

  const mutation = useMutation({
    mutationFn: async ({
      typeKey,
      payload,
    }: {
      typeKey: string
      payload: NotificationTypeTargetingPayload
    }) => {
      const updated = await putNotificationAdminTargeting(typeKey, payload)
      if (!updated) throw new Error("No response from server")
      return updated
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: NOTIFICATION_ADMIN_TARGETING_QUERY_KEY,
      })
    },
  })

  return {
    ...query,
    saveTargeting: mutation.mutateAsync,
    isSaving: mutation.isPending,
    savingTypeKey: mutation.variables?.typeKey ?? null,
  }
}
