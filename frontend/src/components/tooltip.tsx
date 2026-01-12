import type { ReactNode } from "react";
import { InfoIcon } from "lucide-react";

import { cn } from "@/helpers/utils";

interface TooltipProps {
  content: ReactNode;
  contentClassName?: string;
  iconClassName?: string;
  className?: string;
}

export function Tooltip({
  content,
  contentClassName,
  iconClassName,
  className,
}: TooltipProps) {
  return (
    <div className={cn("relative group", className)}>
      <InfoIcon className={cn("text-gray-400 cursor-help", iconClassName)} />
      <div
        className={cn(
          "absolute z-10 invisible opacity-0 group-hover:visible group-hover:opacity-100 transition-opacity bottom-full left-1/2 -translate-x-1/2 mb-2 p-2 bg-gray-800 text-white text-xs rounded shadow-lg",
          contentClassName
        )}
      >
        {content}
        <div className="absolute top-full left-1/2 -translate-x-1/2 w-0 h-0 border-x-4 border-x-transparent border-t-4 border-t-gray-800"></div>
      </div>
    </div>
  );
}
