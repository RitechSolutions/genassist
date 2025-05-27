export type Notification = {
  id: string
  title: string
  description: string
  timestamp: string
  type: "info" | "success" | "warning" | "error"
  read: boolean
} 