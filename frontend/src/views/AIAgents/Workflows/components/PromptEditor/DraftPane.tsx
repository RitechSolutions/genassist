import React, { useId, useState } from "react";
import { Redo2, Save, Undo2 } from "lucide-react";
import { Button } from "@/components/button";
import { Label } from "@/components/label";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/popover";
import { RichInput } from "@/components/richInput";
import { RichTextarea } from "@/components/richTextarea";
import { promptLength, type Gate } from "../../utils/promptEditorGates";
import type { DraftStatus } from "../../utils/promptEditorHistory";
import { GateTooltip } from "./GateTooltip";
import { PromptDiagnostics } from "./PromptDiagnostics";

export interface DraftSaveState {
  gate: Gate;
  enabled: boolean;
  pending: boolean;
  error: string | null;
  submit: (label: string | undefined) => void;
}

export interface DraftStep {
  label: string | null;
  run: () => void;
}

interface DraftPaneProps {
  nodeId: string;
  fieldLabel: string;
  value: string;
  onDraftEdit: (newValue: string) => void;
  canEditPrompt: boolean;
  undo: DraftStep;
  redo: DraftStep;
  status: DraftStatus | null;
  save: DraftSaveState;
}

export const DraftPane: React.FC<DraftPaneProps> = ({
  nodeId,
  fieldLabel,
  value,
  onDraftEdit,
  canEditPrompt,
  undo,
  redo,
  status,
  save,
}) => {
  const labelId = useId();
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
        <div className="flex min-w-0 items-center gap-2">
          <span className="min-w-0 truncate text-sm font-medium">
            Draft · {fieldLabel}
          </span>
          {status && (
            <span className="shrink-0 rounded-md border px-2 py-0.5 text-xs text-muted-foreground">
              {status.label}
            </span>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {save.error && (
            <span className="rounded-md px-2 py-1 text-xs text-destructive bg-destructive/10 border border-destructive/20">
              {save.error}
            </span>
          )}
          <Button
            type="button"
            size="sm"
            variant="ghost"
            onClick={undo.run}
            disabled={undo.label === null}
            title={undo.label === null ? "Undo" : `Undo: ${undo.label}`}
            aria-label={undo.label === null ? "Undo" : `Undo: ${undo.label}`}
          >
            <Undo2 className="h-3.5 w-3.5 mr-2" />
            Undo
          </Button>
          <Button
            type="button"
            size="sm"
            variant="ghost"
            onClick={redo.run}
            disabled={redo.label === null}
            title={redo.label === null ? "Redo" : `Redo: ${redo.label}`}
            aria-label={redo.label === null ? "Redo" : `Redo: ${redo.label}`}
          >
            <Redo2 className="h-3.5 w-3.5 mr-2" />
            Redo
          </Button>
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
                <Label htmlFor={labelId} className="mb-2 block text-xs">
                  Version label (optional)
                </Label>
                <RichInput
                  id={labelId}
                  value={labelDraft}
                  onChange={(e) => setLabelDraft(e.target.value)}
                  placeholder="e.g., Added tone instructions"
                  maxLength={200}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") submit();
                  }}
                />
                <p className="mt-2 text-xs text-muted-foreground">
                  A version is a saved copy. Save the workflow to make the
                  prompt live.
                </p>
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
