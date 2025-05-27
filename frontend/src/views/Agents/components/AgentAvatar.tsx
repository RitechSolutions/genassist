import { useState } from "react";
import { getInitials } from "@/helpers/formatters";

interface AgentAvatarProps {
  firstName: string;
  lastName: string;
  avatarUrl?: string;
  size?: "sm" | "md" | "lg";
}

export function AgentAvatar({ firstName, lastName, avatarUrl, size = "md" }: AgentAvatarProps) {
  const [imageError, setImageError] = useState(false);
  
  // Size classes
  const sizeClasses = {
    sm: "w-8 h-8",
    md: "w-10 h-10", 
    lg: "w-12 h-12"
  };
  
  // Font size classes
  const fontSizeClasses = {
    sm: "text-sm",
    md: "text-base",
    lg: "text-lg"
  };
  
  const initials = getInitials(firstName, lastName);
  
  if (!imageError && avatarUrl) {
    return (
      <img
        src={avatarUrl}
        alt={`${firstName} ${lastName}`}
        className={`${sizeClasses[size]} rounded-full object-cover border border-gray-300`}
        onError={() => setImageError(true)}
      />
    );
  }
  
  return (
    <div className={`${sizeClasses[size]} rounded-full bg-primary/10 text-primary flex items-center justify-center font-semibold ${fontSizeClasses[size]}`}>
      {initials}
    </div>
  );
} 