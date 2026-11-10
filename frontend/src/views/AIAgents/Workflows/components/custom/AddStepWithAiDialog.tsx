import React, { useEffect, useState } from "react";
import { Sparkles } from "lucide-react";

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
            {/* <span className="flex h-7 w-7 items-center justify-center rounded-full bg-[hsl(var(--brand-50))]">
              <Sparkles className="h-4 w-4 text-[hsl(var(--brand-600))]" />
            </span> */}
            Add a step with AI
          </DialogTitle>
          <DialogDescription className="text-xs text-muted-foreground">
            After <span className="font-medium text-foreground">“{nodeName}”</span>
            <span className="mx-1.5 text-muted-foreground/60">·</span>
            output <span className="font-medium text-foreground">{handleLabel}</span>
          </DialogDescription>
        </DialogHeader>
        <div className="px-6 pb-5">
          <AssistantComposer
            value={value}
            onChange={setValue}
            onSubmit={submit}
            size="hero"
            autoFocus={open}
            placeholder="What should happen next?"
            maxLength={BUILDER_MESSAGE_MAX_CHARS}
            onEscape={() => onOpenChange(false)}
            toolbar={<span className="text-[11px] text-muted-foreground">One step, connected to this output. Undo from the chat.</span>}
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
