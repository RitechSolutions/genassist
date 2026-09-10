import React, { useState } from "react";
import { AlertCircle, Copy, GitCompare, Trash2, Undo2 } from "lucide-react";
import { Badge } from "@/components/badge";
import { Button } from "@/components/button";
import { DeleteConfirmationDialog } from "@/components/ui/delete-confirmation-dialog";
import FieldChangeRow from "../diff/FieldChangeRow";
import type { PromptVersion } from "@/interfaces/promptEditor.interface";
import { formatFeedbackDate } from "@/helpers/utils";

const PROMPT_MIN_SIMILARITY = 0.15;

interface VersionPreviewPanelProps {
  version: PromptVersion;
  isLegacy: boolean;
  draft: string;
  isCurrentDraft: boolean;
  fieldLabel: string;
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
  draft,
  isCurrentDraft,
  fieldLabel,
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
  const [isComparing, setIsComparing] = useState(false);
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  // Captured at confirm; prevents retargeting to another row
  const [deleteTargetId, setDeleteTargetId] = useState<string | null>(null);

  const canCopyToHistory = isLegacy && canEdit && !nodeMissing && historyReady;

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

      {isComparing && (
        <div className="px-3 pb-3">
          <FieldChangeRow
            change={{ key: fieldLabel, before: version.content, after: draft }}
            minSimilarity={PROMPT_MIN_SIMILARITY}
          />
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
        <Button
          type="button"
          size="sm"
          variant="outline"
          onClick={() => setIsComparing((comparing) => !comparing)}
        >
          <GitCompare className="h-3.5 w-3.5 mr-2" />
          {isComparing ? "Hide comparison" : "Compare with draft"}
        </Button>
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
