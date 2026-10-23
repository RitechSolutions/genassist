import React from "react";
import * as ToggleGroupPrimitive from "@radix-ui/react-toggle-group";
import {
  BookCheck,
  Braces,
  CircleCheckBig,
  CircleX,
  Database,
  ListChecks,
  MessageSquareQuote,
  Scale,
  Split,
  TextSearch,
  Wrench,
  type LucideIcon,
} from "lucide-react";
import { cn } from "@/helpers/utils";
import type { CheckKind } from "@/interfaces/testEvaluation.interface";
import { CHECK_KINDS } from "../helpers/checks";

const ICONS: Record<CheckKind, LucideIcon> = {
  reply_mentions: TextSearch,
  reply_matches: MessageSquareQuote,
  reply_meets: Scale,
  reply_grounded: BookCheck,
  tool_called: Wrench,
  only_tools: ListChecks,
  step_runs: CircleCheckBig,
  step_fails: CircleX,
  route_taken: Split,
  state_equals: Database,
  value_equals: Braces,
};

/** Every kind of check as a tile, all in view, with what the picked one does below. */
export const CheckKindPicker: React.FC<{ value: CheckKind; onChange: (kind: CheckKind) => void }> = ({
  value,
  onChange,
}) => {
  const picked = CHECK_KINDS.find((kind) => kind.value === value);
  return (
    <div className="space-y-2">
      <ToggleGroupPrimitive.Root
        type="single"
        value={value}
        // Clicking the picked tile again keeps it picked.
        onValueChange={(kind) => kind && onChange(kind as CheckKind)}
        aria-label="Check"
        className="grid grid-cols-3 gap-2 sm:grid-cols-[repeat(auto-fill,minmax(6.25rem,1fr))]"
      >
        {CHECK_KINDS.map((kind) => {
          const Icon = ICONS[kind.value];
          return (
            <ToggleGroupPrimitive.Item
              key={kind.value}
              value={kind.value}
              className={cn(
                "flex min-h-[4.75rem] flex-col items-center justify-center gap-1.5 rounded-lg border bg-background px-2 py-2",
                "text-center text-xs font-medium leading-tight text-muted-foreground transition-colors",
                "hover:border-foreground/30 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                "data-[state=on]:border-primary data-[state=on]:bg-primary/10 data-[state=on]:text-primary",
              )}
            >
              <Icon className="h-5 w-5" aria-hidden="true" />
              {kind.label}
            </ToggleGroupPrimitive.Item>
          );
        })}
      </ToggleGroupPrimitive.Root>
      {picked && <p className="text-xs text-muted-foreground">{picked.description}</p>}
    </div>
  );
};
