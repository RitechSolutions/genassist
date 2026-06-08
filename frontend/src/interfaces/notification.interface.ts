export type Notification = {
  id: string
  notificationId?: string
  typeKey?: string
  groupId?: string
  title: string
  description: string
  timestamp: string
  type: "info" | "success" | "warning" | "error"
  read: boolean
  actionUrl?: string
} 