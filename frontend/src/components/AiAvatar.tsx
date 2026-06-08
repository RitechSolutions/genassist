import { Sparkles } from "lucide-react";

interface AiAvatarProps {
  size?: "sm" | "lg";
}

export const AiAvatar = ({ size = "sm" }: AiAvatarProps) => {
  const sizeClasses =
    size === "lg"
      ? "h-12 w-12 rounded-2xl shadow-lg shadow-ai-brand/20"
      : "h-7 w-7 rounded-lg shadow-sm shadow-ai-brand/15";
  const iconClasses = size === "lg" ? "h-6 w-6" : "h-3.5 w-3.5";

  return (
    <div
      className={`${sizeClasses} shrink-0 bg-gradient-to-br from-ai-brand to-ai-brand-light flex items-center justify-center`}
    >
      <Sparkles className={`${iconClasses} text-white`} />
    </div>
  );
};
