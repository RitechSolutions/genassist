import React from "react";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/RadixTooltip";

interface GateTooltipProps {
  reason: string | null;
  children: React.ReactNode;
}

/**
 * Gate tooltip via span. Disabled buttons block events and tab order,
 * so the span handles hover/focus instead
 */
export const GateTooltip: React.FC<GateTooltipProps> = ({ reason, children }) => {
  if (!reason) return <>{children}</>;

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span className="inline-flex" tabIndex={0}>
          {children}
        </span>
      </TooltipTrigger>
      <TooltipContent side="top" className="max-w-xs">
        {reason}
      </TooltipContent>
    </Tooltip>
  );
};
