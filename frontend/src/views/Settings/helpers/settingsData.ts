import { Bell, Lock, User, Globe } from "lucide-react";
import { SettingSectionType } from "../../../interfaces/settings.interface";

export const settingSections: SettingSectionType[] = [
  {
    title: "Profile Settings",
    icon: User,
    description: "Manage your account information and preferences",
    fields: [
      { label: "Username", type: "text", placeholder: "john23", valueKey: "username", readOnly: true },
      { label: "Email", type: "email", placeholder: "john@example.com", valueKey: "email", readOnly: true },
      { label: "Tenant", type: "text", placeholder: "genassist-support", valueKey: "tenant", readOnly: true }
    ]
  },
  // {
  //   title: "Notification Preferences",
  //   icon: Bell,
  //   description: "Configure how you receive notifications",
  //   fields: [
  //     { label: "Email Notifications", type: "toggle" },
  //     { label: "Desktop Notifications", type: "toggle" },
  //     { label: "Daily Summary", type: "toggle" }
  //   ]
  // },
  // {
  //   title: "Security",
  //   icon: Lock,
  //   description: "Manage your security settings and preferences",
  //   fields: [
  //     { label: "Two-Factor Authentication", type: "toggle" },
  //     { label: "Session Timeout (minutes)", type: "number", placeholder: "30" }
  //   ]
  // },
  // {
  //   title: "Language & Region",
  //   icon: Globe,
  //   description: "Set your language and regional preferences",
  //   fields: [
  //     { label: "Language", type: "select", options: ["English", "Spanish", "French"] },
  //     { label: "Time Zone", type: "select", options: ["UTC", "UTC+1", "UTC-5"] }
  //   ]
  // }
]; 
