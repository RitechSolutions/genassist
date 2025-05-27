import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/card"
import { Clock } from "lucide-react"
import { Notification } from "../../../interfaces/notification.interface"

interface NotificationCardProps {
  notification: Notification
}

export const NotificationCard = ({ notification }: NotificationCardProps) => {
  const typeStyles = {
    info: "bg-blue-50 border-blue-200",
    success: "bg-green-50 border-green-200",
    warning: "bg-yellow-50 border-yellow-200",
    error: "bg-red-50 border-red-200"
  }

  return (
    <Card className={`mb-4 ${!notification.read ? typeStyles[notification.type] : ''}`}>
      <CardHeader className="flex flex-row items-start justify-between space-y-0 pb-2">
        <CardTitle className="text-base font-semibold">
          {notification.title}
        </CardTitle>
        <div className="flex items-center gap-2">
          <span className="text-sm text-muted-foreground flex items-center gap-1">
            <Clock className="h-3 w-3" />
            {notification.timestamp}
          </span>
          {!notification.read && (
            <div className="h-2 w-2 rounded-full bg-blue-500" />
          )}
        </div>
      </CardHeader>
      <CardContent>
        <CardDescription>{notification.description}</CardDescription>
      </CardContent>
    </Card>
  )
} 