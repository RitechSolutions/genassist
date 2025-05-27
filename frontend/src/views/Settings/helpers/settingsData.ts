import { Bell, Lock, User, Globe } from "lucide-react";
import { SettingSectionType } from "../../../interfaces/settings.interface";

export const settingSections: SettingSectionType[] = [
  {
    title: "Profile Settings",
    icon: User,
    description: "Manage your account information and preferences",
    fields: [
      { label: "Full Name", type: "text", placeholder: "John Doe" },
      { label: "Email", type: "email", placeholder: "john@example.com" },
      { label: "Role", type: "text", placeholder: "Support Operator" }
    ]
  },
  {
    title: "Notification Preferences",
    icon: Bell,
    description: "Configure how you receive notifications",
    fields: [
      { label: "Email Notifications", type: "toggle" },
      { label: "Desktop Notifications", type: "toggle" },
      { label: "Daily Summary", type: "toggle" }
    ]
  },
  {
    title: "Security",
    icon: Lock,
    description: "Manage your security settings and preferences",
    fields: [
      { label: "Two-Factor Authentication", type: "toggle" },
      { label: "Session Timeout (minutes)", type: "number", placeholder: "30" }
    ]
  },
  {
    title: "Language & Region",
    icon: Globe,
    description: "Set your language and regional preferences",
    fields: [
      { label: "Language", type: "select", options: ["English", "Spanish", "French"] },
      { label: "Time Zone", type: "select", options: ["UTC", "UTC+1", "UTC-5"] }
    ]
  }
]; 