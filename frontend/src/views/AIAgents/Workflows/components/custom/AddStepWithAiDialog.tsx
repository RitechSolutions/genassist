import React, { useEffect, useState } from "react";
import { ArrowRight } from "lucide-react";

import { GenAssistMark } from "@/components/AssistantEmptyState";

import { AssistantComposer } from "@/components/AssistantComposer";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/dialog";
import { BUILDER_MESSAGE_MAX_CHARS } from "@/views/AIAgents/Workflows/utils/builderLimits";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** The step the new one comes after, and the name of its output. */
  nodeName: string;
  handleLabel: string;
  onSubmit: (instruction: string) => void;
}

const QUICK_IDEAS = [
  "Reply to the customer with a short confirmation",
  "Summarize the message in one sentence",
  "Send a Slack message with the details",
  "Ask the customer for their order number",
];

/**
 * "Add with AI" on an output handle: one sentence becomes one step, designed to
 * fit what comes before it, connected to this output and highlighted on the
 * canvas so it can be kept or undone.
 */
export const AddStepWithAiDialog: React.FC<Props> = ({ open, onOpenChange, nodeName, handleLabel, onSubmit }) => {
  const [value, setValue] = useState("");
  useEffect(() => {
    if (!open) setValue("");
  }, [open]);

  const submit = (instruction: string) => {
    onSubmit(instruction);
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="z-[2000] w-[min(92vw,560px)] max-w-[560px] gap-0 overflow-hidden rounded-2xl border border-border p-0 shadow-2xl">
        <DialogHeader className="space-y-1 px-6 pb-3 pt-5 text-left">
          <DialogTitle className="flex items-center gap-2 text-base font-semibold">
            <GenAssistMark className="h-6 w-6 text-zinc-700 dark:text-white" />
            Add a step with GenAgent
          </DialogTitle>
          <DialogDescription className="flex flex-wrap items-center gap-1.5 pt-1 text-xs text-muted-foreground">
            <span>After</span>
            <span className="inline-flex max-w-[260px] items-center truncate rounded-md border border-border bg-muted/50 px-2 py-0.5 font-medium text-foreground">
              {nodeName}
            </span>
            <ArrowRight className="h-3 w-3 text-muted-foreground/70" aria-hidden />
            <span className="inline-flex items-center rounded-md bg-[hsl(var(--brand-600))]/10 px-2 py-0.5 font-medium text-[hsl(var(--brand-600))]">
              {handleLabel}
            </span>
          </DialogDescription>
        </DialogHeader>
        <div className="px-6 pb-5">
          <AssistantComposer
            value={value}
            onChange={setValue}
            onSubmit={submit}
            // A plain one-line field (nothing else to show in the box); it still grows with long text.
            size="inline"
            noIcon
            autoFocus={open}
            placeholder="What should happen next?"
            maxLength={BUILDER_MESSAGE_MAX_CHARS}
            onEscape={() => onOpenChange(false)}
          />
          {/* <div className="mt-3 flex flex-wrap gap-1.5">
            {QUICK_IDEAS.map((idea) => (
              <button
                key={idea}
                type="button"
                onClick={() => setValue(idea)}
                className="rounded-full border border-border bg-muted/40 px-2.5 py-1 text-[11px] text-foreground transition-colors hover:border-[hsl(var(--brand-600))]/50 hover:bg-[hsl(var(--brand-600))]/5"
              >
                {idea}
              </button>
            ))}
          </div> */}
        </div>
      </DialogContent>
    </Dialog>
  );
};
