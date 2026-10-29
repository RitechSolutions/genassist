import { ReactNode, useRef, useState } from "react";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/RadixTooltip";
import { cn } from "@/helpers/utils";

/** One line of text that shows in full in a tooltip, only while it is cut off */
export function TruncatedText({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  const ref = useRef<HTMLSpanElement>(null);
  const [open, setOpen] = useState(false);

  const handleOpenChange = (next: boolean) => {
    const el = ref.current;
    setOpen(next && !!el && el.scrollWidth > el.clientWidth);
  };

  return (
    <TooltipProvider delayDuration={200}>
      <Tooltip open={open} onOpenChange={handleOpenChange}>
        <TooltipTrigger asChild>
          <span ref={ref} className={cn("block truncate", className)}>
            {children}
          </span>
        </TooltipTrigger>
        <TooltipContent className="max-w-[min(28rem,var(--radix-tooltip-content-available-width,28rem))] p-0">
          <div className="max-h-[var(--radix-tooltip-content-available-height,24rem)] overflow-y-auto whitespace-pre-wrap break-words px-3 py-1.5">
            {children}
          </div>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
