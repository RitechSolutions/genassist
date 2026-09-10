import React, { useState } from "react";
import {
  AlertCircle,
  ChevronDown,
  ChevronRight,
  History,
  Link2,
  MoreVertical,
  Trash2,
} from "lucide-react";
import { Badge } from "@/components/badge";
import { Button } from "@/components/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/dropdown-menu";
import { DeleteConfirmationDialog } from "@/components/ui/delete-confirmation-dialog";
import { cn } from "@/lib/utils";
import type {
  LegacyPromptHistory,
  PromptVersion,
} from "@/interfaces/promptEditor.interface";
import { formatFeedbackDate } from "@/helpers/utils";
import type { HistoryState } from "../../utils/promptEditorGates";

interface VersionsSidebarProps {
  versions: PromptVersion[];
  legacy: LegacyPromptHistory | null;
  selectedVersionId: string | null;
  onSelect: (versionId: string) => void;
  canEditPrompt: boolean;
  currentGoldSuiteId: string | null;
  onLinkLegacyDataset: () => void;
  linkPending: boolean;
  linkError: string | null;
  status: HistoryState["status"];
  /** Legacy rows live under another node, so the caller routes the cache refresh */
  onDelete: (versionId: string, isLegacy: boolean) => void;
  deletingVersionId: string | null;
  deleteError: string | null;
}

interface DeleteTarget {
  version: PromptVersion;
  isLegacy: boolean;
}

interface VersionRowProps {
  version: PromptVersion;
  isLegacy: boolean;
  isSelected: boolean;
  canDelete: boolean;
  isDeleting: boolean;
  deletePending: boolean;
  onSelect: (versionId: string) => void;
  onRequestDelete: (target: DeleteTarget) => void;
}

const VersionRow: React.FC<VersionRowProps> = ({
  version,
  isLegacy,
  isSelected,
  canDelete,
  isDeleting,
  deletePending,
  onSelect,
  onRequestDelete,
}) => (
  <div
    className={cn(
      "flex items-start gap-1 rounded-md border py-2 pl-3 pr-1 transition-colors",
      "hover:bg-muted/40 focus-within:ring-2 focus-within:ring-ring",
      isSelected
        ? "bg-blue-50 border-blue-200 dark:bg-blue-500/15 dark:border-blue-500/30"
        : "bg-card",
    )}
  >
    <button
      type="button"
      className="min-w-0 flex-1 text-left focus:outline-none"
      aria-pressed={isSelected}
      onClick={() => onSelect(version.id)}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <span className="text-sm font-medium">v{version.version_number}</span>
          <div className="text-xs text-muted-foreground truncate">
            {version.label || formatFeedbackDate(version.created_at)}
          </div>
        </div>
        <div className="text-xs text-muted-foreground shrink-0">
          {formatFeedbackDate(version.created_at)}
        </div>
      </div>
    </button>

    {canDelete && (
      // Non-modal so the confirm dialog stays internal
      <DropdownMenu modal={false}>
        <DropdownMenuTrigger asChild>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="h-7 w-7 shrink-0"
            aria-label={`Actions for ${isLegacy ? "legacy " : ""}v${version.version_number}`}
          >
            <MoreVertical className="h-4 w-4" />
          </Button>
        </DropdownMenuTrigger>
        {/* Above prompt editor (z-[1350]) */}
        <DropdownMenuContent align="end" className="z-[1400]">
          <DropdownMenuItem
            className="text-destructive focus:text-destructive"
            disabled={deletePending}
            // Menu closes on select and would dismiss dialog in the same tick. Defer to next tick
            onSelect={() =>
              window.setTimeout(() => onRequestDelete({ version, isLegacy }), 0)
            }
          >
            <Trash2 className="mr-2 h-4 w-4" />
            <span>{isDeleting ? "Deleting…" : "Delete"}</span>
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    )}
  </div>
);

export const VersionsSidebar: React.FC<VersionsSidebarProps> = ({
  versions,
  legacy,
  selectedVersionId,
  onSelect,
  canEditPrompt,
  currentGoldSuiteId,
  onLinkLegacyDataset,
  linkPending,
  linkError,
  status,
  onDelete,
  deletingVersionId,
  deleteError,
}) => {
  const [isLegacyOpen, setIsLegacyOpen] = useState(false);
  // Captured at confirm; prevents retargeting to another row
  const [deleteTarget, setDeleteTarget] = useState<DeleteTarget | null>(null);

  if (status !== "ready") {
    // Unreadable history ≠ empty
    return (
      <div className="flex items-center justify-center py-8 text-muted-foreground text-sm">
        {status === "pending" ? "Loading history…" : "History unavailable"}
      </div>
    );
  }

  const canLinkLegacyDataset =
    !!legacy?.gold_suite_id && !currentGoldSuiteId && canEditPrompt;

  // One delete at a time; the id match only picks which row reports progress
  const deletePending = deletingVersionId !== null;

  const rowProps = (version: PromptVersion, isLegacy: boolean) => ({
    version,
    isLegacy,
    isSelected: selectedVersionId === version.id,
    canDelete: canEditPrompt,
    isDeleting: deletingVersionId === version.id,
    deletePending,
    onSelect,
    onRequestDelete: setDeleteTarget,
  });

  return (
    <div className="space-y-3">
      {deleteError && (
        <div className="flex items-start gap-2 text-destructive text-xs bg-destructive/10 border border-destructive/20 rounded-md px-2 py-1">
          <AlertCircle className="h-3.5 w-3.5 shrink-0 mt-px" />
          <span>{deleteError}</span>
        </div>
      )}

      {versions.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-10 text-muted-foreground gap-2 text-center">
          <History className="h-7 w-7" />
          <div className="text-sm font-medium">No versions yet</div>
          <div className="text-xs">
            Save a version from the Editor to start tracking changes.
          </div>
        </div>
      ) : (
        <div className="space-y-1 p-1">
          {versions.map((version) => (
            <VersionRow key={version.id} {...rowProps(version, false)} />
          ))}
        </div>
      )}

      {legacy && (
        <div className="border-t pt-2">
          <button
            type="button"
            onClick={() => setIsLegacyOpen((open) => !open)}
            className="flex w-full items-center gap-1 text-xs font-medium text-muted-foreground hover:text-foreground transition-colors"
            aria-expanded={isLegacyOpen}
          >
            {isLegacyOpen ? (
              <ChevronDown className="h-3.5 w-3.5" />
            ) : (
              <ChevronRight className="h-3.5 w-3.5" />
            )}
            Older shared history
            <Badge variant="outline" className="ml-auto text-[9px] px-1.5">
              {legacy.versions.length}
            </Badge>
          </button>

          {isLegacyOpen && (
            <div className="mt-2 space-y-1 p-1">
              {legacy.versions.map((version) => (
                <VersionRow key={version.id} {...rowProps(version, true)} />
              ))}
              {canLinkLegacyDataset && (
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="w-full mt-2"
                  onClick={onLinkLegacyDataset}
                  disabled={linkPending}
                >
                  <Link2 className="h-3.5 w-3.5 mr-2" />
                  {linkPending ? "Linking…" : "Link this dataset"}
                </Button>
              )}
              {linkError && (
                <div className="flex items-start gap-2 text-destructive text-xs bg-destructive/10 border border-destructive/20 rounded-md px-2 py-1 mt-2">
                  <AlertCircle className="h-3.5 w-3.5 shrink-0 mt-px" />
                  <span>{linkError}</span>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      <DeleteConfirmationDialog
        open={deleteTarget !== null}
        onOpenChange={(open) => {
          if (!open) setDeleteTarget(null);
        }}
        title="Delete version?"
        description={
          deleteTarget?.isLegacy
          ? "This version is shared with the other nodes in this workflow. Deleting it removes it from all of them, and this can't be undone."
          : "This version will no longer show in the history. This can't be undone."
        }

        onConfirm={() => {
          if (deleteTarget)
            onDelete(deleteTarget.version.id, deleteTarget.isLegacy);
        }}
        isDeleting={deletingVersionId === deleteTarget?.version.id}
      />
    </div>
  );
};
