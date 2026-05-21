import { apiRequest } from "@/config/api"

type MarkNotificationsReadResponse = {
  marked_count: number
}

export async function markNotificationsRead(
  notificationIds: string[]
): Promise<number | null> {
  const unique = [...new Set(notificationIds.filter(Boolean))]
  if (unique.length === 0) return 0
  try {
    const response = await apiRequest<MarkNotificationsReadResponse>(
      "post",
      "/notifications/reads",
      { notification_ids: unique }
    )
    return response?.marked_count ?? null
  } catch (error) {
    console.error("Error marking notifications as read:", error)
    return null
  }
}
