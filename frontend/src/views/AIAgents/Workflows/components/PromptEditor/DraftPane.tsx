import React, { useState } from "react";
import { Save } from "lucide-react";
import { Button } from "@/components/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/popover";
import { RichInput } from "@/components/richInput";
import { RichTextarea } from "@/components/richTextarea";
import { promptLength, type Gate } from "../../utils/promptEditorGates";
import { GateTooltip } from "./GateTooltip";
import { PromptDiagnostics } from "./PromptDiagnostics";

export interface DraftSaveState {
  gate: Gate;
  enabled: boolean;
  pending: boolean;
  status: { type: "success" | "error"; message: string } | null;
  submit: (label: string | undefined) => void;
}

interface DraftPaneProps {
  nodeId: string;
  fieldLabel: string;
  value: string;
  onDraftEdit: (newValue: string) => void;
  canEditPrompt: boolean;
  save: DraftSaveState;
}

export const DraftPane: React.FC<DraftPaneProps> = ({
  nodeId,
  fieldLabel,
  value,
  onDraftEdit,
  canEditPrompt,
  save,
}) => {
  const [isLabelOpen, setIsLabelOpen] = useState(false);
  const [labelDraft, setLabelDraft] = useState("");

  const submit = () => {
    if (!save.enabled) return;
    const trimmed = labelDraft.trim();
    save.submit(trimmed ? trimmed : undefined);
    setIsLabelOpen(false);
    setLabelDraft("");
  };

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <div className="flex shrink-0 flex-wrap items-center justify-between gap-2 border-b px-4 py-2">
        <span className="min-w-0 truncate text-sm font-medium">
          Draft · {fieldLabel}
        </span>
        <div className="flex items-center gap-2">
          {save.status && (
            <span
              className={`rounded-md px-2 py-1 text-xs ${
                save.status.type === "error"
                  ? "text-destructive bg-destructive/10 border border-destructive/20"
                  : "text-green-700 dark:text-green-400 bg-green-50 dark:bg-green-500/15 border border-green-200 dark:border-green-500/30"
              }`}
            >
              {save.status.message}
            </span>
          )}
          {canEditPrompt && (
            <Popover open={isLabelOpen} onOpenChange={setIsLabelOpen}>
              <GateTooltip reason={save.gate.reason}>
                <PopoverTrigger asChild>
                  <Button size="sm" disabled={!save.enabled}>
                    <Save className="h-4 w-4 mr-2" />
                    {save.pending ? "Saving..." : "Save Version"}
                  </Button>
                </PopoverTrigger>
              </GateTooltip>
              <PopoverContent align="end" className="z-[1400] w-80">
                <div className="mb-2 text-xs font-medium">
                  Version label (optional)
                </div>
                <RichInput
                  value={labelDraft}
                  onChange={(e) => setLabelDraft(e.target.value)}
                  placeholder="e.g., Added tone instructions"
                  maxLength={200}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") submit();
                  }}
                />
                <div className="mt-3 flex justify-end gap-2">
                  <Button
                    type="button"
                    size="sm"
                    variant="ghost"
                    onClick={() => setIsLabelOpen(false)}
                  >
                    Cancel
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    onClick={submit}
                    disabled={!save.enabled}
                  >
                    Save
                  </Button>
                </div>
              </PopoverContent>
            </Popover>
          )}
        </div>
      </div>

      <div className="min-h-0 flex-1 px-4 pt-3">
        <RichTextarea
          fill
          value={value}
          onChange={(e) => onDraftEdit(e.target.value)}
          placeholder="Enter your prompt..."
          className="w-full font-mono text-sm"
        />
      </div>

      <div className="shrink-0 px-4 pt-1 text-right text-xs text-muted-foreground">
        {promptLength(value)} characters
      </div>

      <div className="shrink-0 px-4 pb-3 pt-2 empty:hidden">
        <PromptDiagnostics nodeId={nodeId} value={value} />
      </div>
    </div>
  );
};
