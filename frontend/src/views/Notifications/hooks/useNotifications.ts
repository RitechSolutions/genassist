import { useState } from "react"
import { Notification } from "../../../interfaces/notification.interface"
import { toast } from "react-hot-toast"

// Sample data for notifications
const sampleNotifications: Notification[] = [
  {
    id: "1",
    title: "New Customer Transcript Available",
    description: "A new conversation with customer ID #1234 has been processed and is ready for review.",
    timestamp: "Just now",
    type: "info",
    read: false
  },
  {
    id: "2",
    title: "Weekly Performance Report",
    description: "Your weekly performance metrics have been updated. View your latest statistics.",
    timestamp: "2 hours ago",
    type: "success",
    read: false
  },
  {
    id: "3",
    title: "System Maintenance Notice",
    description: "Scheduled maintenance will occur on Saturday at 2 AM EST. Service interruptions may occur.",
    timestamp: "1 day ago",
    type: "warning",
    read: true
  },
  {
    id: "4",
    title: "New Feature Available",
    description: "Check out our new analytics dashboard with improved visualization options.",
    timestamp: "2 days ago",
    type: "info",
    read: true
  }
]

export const useNotifications = () => {
  const [notifications, setNotifications] = useState<Notification[]>(sampleNotifications)

  const markAllAsRead = () => {
    setNotifications(prev => 
      prev.map(notification => ({ ...notification, read: true }))
    )
    toast.success("All notifications marked as read")
  }

  const markAsRead = (id: string) => {
    setNotifications(prev => 
      prev.map(notification => 
        notification.id === id 
          ? { ...notification, read: true } 
          : notification
      )
    )
  }

  return {
    notifications,
    markAllAsRead,
    markAsRead
  }
} 