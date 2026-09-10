import React, { useId, useState } from "react";
import { AlertCircle, Copy, Trash2, Undo2 } from "lucide-react";
import { Badge } from "@/components/badge";
import { Button } from "@/components/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/select";
import { DeleteConfirmationDialog } from "@/components/ui/delete-confirmation-dialog";
import FieldChangeRow from "../diff/FieldChangeRow";
import type { PromptVersion } from "@/interfaces/promptEditor.interface";
import { formatFeedbackDate } from "@/helpers/utils";
import {
  diffSides,
  findPromptVersion,
  type HistoryEntry,
} from "../../utils/promptEditorHistory";

const PROMPT_MIN_SIMILARITY = 0.15;

// Sentinels for non-version choices (Radix Select has no empty-string value)
const DRAFT_TARGET = "__draft__";
const NO_TARGET = "__none__";

interface VersionPreviewPanelProps {
  version: PromptVersion;
  isLegacy: boolean;
  versions: readonly PromptVersion[];
  legacyVersions: readonly PromptVersion[];
  draft: string;
  isCurrentDraft: boolean;
  canEdit: boolean;
  canUndo: boolean;
  nodeMissing: boolean;
  historyReady: boolean;
  onApply: () => void;
  onUndo: () => void;
  onCopy: () => void;
  onDelete: (versionId: string) => void;
  isCopying: boolean;
  copyError: string | null;
  isDeleting: boolean;
  deleteError: string | null;
}

export const VersionPreviewPanel: React.FC<VersionPreviewPanelProps> = ({
  version,
  isLegacy,
  versions,
  legacyVersions,
  draft,
  isCurrentDraft,
  canEdit,
  canUndo,
  nodeMissing,
  historyReady,
  onApply,
  onUndo,
  onCopy,
  onDelete,
  isCopying,
  copyError,
  isDeleting,
  deleteError,
}) => {
  const compareId = useId();
  const [compareTargetId, setCompareTargetId] = useState(NO_TARGET);
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  // Captured at confirm; prevents retargeting to another row
  const [deleteTargetId, setDeleteTargetId] = useState<string | null>(null);

  const canCopyToHistory = isLegacy && canEdit && !nodeMissing && historyReady;

  const previewed: HistoryEntry = { version, isLegacy };
  // A target deleted while selected stays stored but resolves to nothing, so no diff renders
  const targetEntry =
    compareTargetId === DRAFT_TARGET || compareTargetId === NO_TARGET
      ? null
      : findPromptVersion(versions, legacyVersions, compareTargetId);
  const comparison =
    compareTargetId === DRAFT_TARGET
      ? diffSides(previewed, "draft", draft)
      : targetEntry
        ? diffSides(previewed, targetEntry, draft)
        : null;
  const selectValue =
    compareTargetId === DRAFT_TARGET
      ? DRAFT_TARGET
      : targetEntry
        ? targetEntry.version.id
        : NO_TARGET;

  return (
    <div className="rounded-md border bg-card mb-4">
      <div className="flex flex-wrap items-center gap-2 border-b px-3 py-2">
        <span className="text-sm font-medium">v{version.version_number}</span>
        <span className="text-xs text-muted-foreground truncate">
          {version.label || formatFeedbackDate(version.created_at)}
        </span>
        {isCurrentDraft && (
          <Badge variant="success" className="text-[9px] px-1.5">
            Current draft
          </Badge>
        )}
        {isLegacy && (
          <Badge variant="outline" className="text-[9px] px-1.5">
            Legacy
          </Badge>
        )}
      </div>

      <pre className="max-h-48 overflow-y-auto whitespace-pre-wrap break-words px-3 py-2 font-mono text-xs text-muted-foreground">
        {version.content}
      </pre>

      {comparison && (
        <div className="px-3 pb-3">
          {comparison.before === comparison.after ? (
            <div className="overflow-hidden rounded-md border border-border bg-card">
              <div className="border-b border-border bg-muted/80 px-2.5 py-1 font-mono text-[11px] font-medium text-muted-foreground">
                {comparison.label}
              </div>
              <p className="px-2.5 py-2 text-[11px] italic text-muted-foreground">
                No differences
              </p>
            </div>
          ) : (
            <FieldChangeRow
              change={{
                key: comparison.label,
                before: comparison.before,
                after: comparison.after,
              }}
              minSimilarity={PROMPT_MIN_SIMILARITY}
            />
          )}
        </div>
      )}

      {(copyError || deleteError) && (
        <div className="px-3 pb-2 space-y-2">
          {[copyError, deleteError].map(
            (message, index) =>
              message && (
                <div
                  key={index}
                  className="flex items-start gap-2 text-destructive text-xs bg-destructive/10 border border-destructive/20 rounded-md px-2 py-1"
                >
                  <AlertCircle className="h-3.5 w-3.5 shrink-0 mt-px" />
                  <span>{message}</span>
                </div>
              ),
          )}
        </div>
      )}

      <div className="flex flex-wrap gap-2 border-t px-3 py-2">
        <div className="flex items-center gap-2">
          <span
            id={`${compareId}-label`}
            className="text-xs text-muted-foreground"
          >
            Compare with
          </span>
          <Select value={selectValue} onValueChange={setCompareTargetId}>
            <SelectTrigger
              id={`${compareId}-trigger`}
              className="h-9 w-auto max-w-56 text-xs"
              aria-labelledby={`${compareId}-label ${compareId}-trigger`}
            >
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={DRAFT_TARGET}>Current draft</SelectItem>
              {versions
                .filter((v) => v.id !== version.id)
                .map((v) => (
                  <SelectItem key={v.id} value={v.id}>
                    v{v.version_number}
                  </SelectItem>
                ))}
              {legacyVersions
                .filter((v) => v.id !== version.id)
                .map((v) => (
                  <SelectItem key={v.id} value={v.id}>
                    v{v.version_number} · Legacy
                  </SelectItem>
                ))}
              <SelectItem value={NO_TARGET}>No comparison</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <Button type="button" size="sm" onClick={onApply} disabled={isCurrentDraft}>
          Apply to draft
        </Button>
        {canUndo && (
          <Button type="button" size="sm" variant="ghost" onClick={onUndo}>
            <Undo2 className="h-3.5 w-3.5 mr-2" />
            Undo
          </Button>
        )}
        {canCopyToHistory && (
          <Button
            type="button"
            size="sm"
            variant="outline"
            onClick={onCopy}
            disabled={isCopying}
          >
            <Copy className="h-3.5 w-3.5 mr-2" />
            {isCopying ? "Copying…" : "Copy into this history"}
          </Button>
        )}
        {canEdit && historyReady && (
          <Button
            type="button"
            size="sm"
            variant="ghost"
            className="text-destructive hover:text-destructive"
            onClick={() => {
              setDeleteTargetId(version.id);
              setIsDeleteDialogOpen(true);
            }}
            disabled={isDeleting}
          >
            <Trash2 className="h-3.5 w-3.5 mr-2" />
            {isDeleting ? "Deleting…" : "Delete"}
          </Button>
        )}
      </div>

      <DeleteConfirmationDialog
        open={isDeleteDialogOpen}
        onOpenChange={(open) => {
          setIsDeleteDialogOpen(open);
          if (!open) setDeleteTargetId(null);
        }}
        title="Delete version?"
        description="The version is hidden from this history."
        onConfirm={() => {
          if (deleteTargetId) onDelete(deleteTargetId);
        }}
        isDeleting={isDeleting}
      />
    </div>
  );
};
