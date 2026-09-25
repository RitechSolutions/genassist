import { Columns3, Rows3 } from "lucide-react";

import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/RadixTooltip";
import { cn } from "@/helpers/utils";

import type { ConversationsViewMode } from "../../helpers/conversationsView";

const OPTIONS: { value: ConversationsViewMode; label: string; hint: string; icon: typeof Rows3 }[] = [
  { value: "list", label: "List", hint: "One conversation per row", icon: Rows3 },
  { value: "split", label: "Split", hint: "List, conversation and stats side by side", icon: Columns3 },
];

type ConversationsViewSwitchProps = {
  value: ConversationsViewMode;
  onChange: (value: ConversationsViewMode) => void;
  className?: string;
};

/** Segmented control that swaps the whole Conversations page between list and split view. */
export function ConversationsViewSwitch({ value, onChange, className }: ConversationsViewSwitchProps) {
  return (
    <div
      role="group"
      aria-label="Conversations view"
      className={cn(
        "inline-flex h-9 shrink-0 items-center gap-0.5 rounded-md border border-input bg-card p-0.5",
        className
      )}
    >
      {OPTIONS.map((option) => {
        const Icon = option.icon;
        const isActive = value === option.value;
        return (
          <Tooltip key={option.value}>
            <TooltipTrigger asChild>
              <button
                type="button"
                aria-pressed={isActive}
                onClick={() => onChange(option.value)}
                className={cn(
                  "flex h-8 items-center gap-1.5 rounded px-2.5 text-xs font-medium transition-colors",
                  isActive
                    ? "bg-primary/10 text-foreground"
                    : "text-muted-foreground hover:bg-muted hover:text-foreground"
                )}
              >
                <Icon className="h-3.5 w-3.5 shrink-0" />
                <span className="hidden sm:inline">{option.label}</span>
              </button>
            </TooltipTrigger>
            <TooltipContent>{option.hint}</TooltipContent>
          </Tooltip>
        );
      })}
    </div>
  );
}
