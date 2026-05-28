import { Notification } from "@/interfaces/notification.interface"

export const CONVERSATION_STARTED_DESCRIPTION_PREFIX =
  "A new conversation has started"

function extractConversationIdFromUrl(actionUrl?: string): string | null {
  if (!actionUrl) return null
  const match = actionUrl.match(/[?&]conversation=([a-f0-9-]+)/i)
  return match?.[1] ?? null
}

export function formatConversationStartedDescription(shortId: string): string {
  return `${CONVERSATION_STARTED_DESCRIPTION_PREFIX} ${shortId}.`
}

export function getConversationShortId(notification: Notification): string | null {
  const shortFromDescription =
    notification.description.match(/#([a-f0-9]{4})\b/i)?.[0] ??
    notification.description.match(/^#([a-f0-9]{4})$/i)?.[0]
  if (shortFromDescription) return shortFromDescription.toLowerCase()

  const rawId =
    extractConversationIdFromUrl(notification.actionUrl) ??
    notification.description.match(/\(ID:\s*([a-f0-9-]+)\.{0,3}\)/i)?.[1] ??
    notification.description.match(/Conversation\s+([a-f0-9-]+)\.{3}/i)?.[1] ??
    null
  if (!rawId) return null
  return `#${rawId.replace(/-/g, "").slice(-4)}`
}

export function formatNotificationDescription(notification: Notification): string {
  const shortId = getConversationShortId(notification)
  if (!shortId) return notification.description

  if (notification.typeKey === "conversation_started") {
    return formatConversationStartedDescription(shortId)
  }

  return notification.description
    .replace(/\(ID:\s*[^)]+\)/gi, shortId)
    .replace(/Conversation\s+[a-f0-9-]+\.{3}/gi, `Conversation ${shortId}`)
}
