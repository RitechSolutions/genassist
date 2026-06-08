import { apiRequest } from "@/config/api"

export type NotificationTypeTargeting = {
  typeKey: string
  allowAllTenantUsers: boolean
  userIds: string[]
  groupIds: string[]
}

type NotificationTypeTargetingRaw = {
  type_key: string
  allow_all_tenant_users: boolean
  user_ids: string[]
  group_ids: string[]
}

type NotificationAdminTargetingRaw = {
  types: NotificationTypeTargetingRaw[]
}

function mapType(raw: NotificationTypeTargetingRaw): NotificationTypeTargeting {
  return {
    typeKey: raw.type_key,
    allowAllTenantUsers: raw.allow_all_tenant_users,
    userIds: raw.user_ids ?? [],
    groupIds: raw.group_ids ?? [],
  }
}

export async function fetchNotificationAdminTargeting(): Promise<
  NotificationTypeTargeting[] | null
> {
  try {
    const response = await apiRequest<NotificationAdminTargetingRaw>(
      "get",
      "/notifications/admin/targeting"
    )
    if (!response?.types) return null
    return response.types.map(mapType)
  } catch (error) {
    console.error("Error fetching notification admin targeting:", error)
    return null
  }
}

export type NotificationTypeTargetingPayload = {
  allowAllTenantUsers: boolean
  userIds: string[]
  groupIds: string[]
}

export async function putNotificationAdminTargeting(
  typeKey: string,
  payload: NotificationTypeTargetingPayload
): Promise<NotificationTypeTargeting | null> {
  try {
    const body = {
      allow_all_tenant_users: payload.allowAllTenantUsers,
      user_ids: payload.userIds,
      group_ids: payload.groupIds,
    }
    const response = await apiRequest<NotificationTypeTargetingRaw>(
      "put",
      `/notifications/admin/targeting/${encodeURIComponent(typeKey)}`,
      body
    )
    if (!response) return null
    return mapType(response)
  } catch (error) {
    console.error("Error updating notification admin targeting:", error)
    throw error
  }
}
