import React, { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { History, Trash2 } from "lucide-react";
import { Badge } from "@/components/badge";
import { Button } from "@/components/button";
import { DeleteConfirmationDialog } from "@/components/ui/delete-confirmation-dialog";
import { cn } from "@/lib/utils";
import {
  deletePromptVersion,
  listPromptVersions,
  restorePromptVersion,
} from "@/services/promptEditor";
import type { PromptVersion } from "@/interfaces/promptEditor.interface";
import { formatFeedbackDate } from "@/helpers/utils";

interface VersionsSidebarProps {
  workflowId: string;
  nodeId: string;
  promptField: string;
  selectedVersionId: string | null;
  onSelectedVersionIdChange: (versionId: string) => void;
  onRestore: (content: string) => void;
}

export const VersionsSidebar: React.FC<VersionsSidebarProps> = ({
  workflowId,
  nodeId,
  promptField,
  selectedVersionId,
  onSelectedVersionIdChange,
  onRestore,
}) => {
  const queryClient = useQueryClient();
  const queryKey = ["promptVersions", workflowId, nodeId, promptField];
  const [deleteTargetId, setDeleteTargetId] = useState<string | null>(null);
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);

  const { data: versions = [], isLoading } = useQuery({
    queryKey,
    queryFn: () => listPromptVersions(workflowId, nodeId, promptField),
    select: (data) => (data ?? []) as PromptVersion[],
  });

  useEffect(() => {
    if (!selectedVersionId && versions.length > 0) {
      const active = versions.find((v) => v.is_active);
      onSelectedVersionIdChange(active?.id ?? versions[0]!.id);
    }
  }, [versions, selectedVersionId, onSelectedVersionIdChange]);

  const restoreMutation = useMutation({
    mutationFn: (versionId: string) => restorePromptVersion(versionId),
    onSuccess: (restored) => {
      queryClient.invalidateQueries({ queryKey });
      if (restored) {
        onRestore(restored.content);
      }
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (versionId: string) => deletePromptVersion(versionId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey });
    },
  });

  const deleteTarget = useMemo(() => {
    if (!deleteTargetId) return null;
    return versions.find((v) => v.id === deleteTargetId) ?? null;
  }, [deleteTargetId, versions]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-8 text-muted-foreground text-sm">
        Loading versions...
      </div>
    );
  }

  if (versions.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-10 text-muted-foreground gap-2 text-center">
        <History className="h-7 w-7" />
        <div className="text-sm font-medium">No versions yet</div>
        <div className="text-xs">
          Save a version from the Editor to start tracking changes.
        </div>
      </div>
    );
  }

  return (
    <>
      <div className="space-y-1 p-1">
      {versions.map((version) => {
        const isSelected =
          selectedVersionId === version.id ||
          (!selectedVersionId && version.is_active);

        return (
          <div
            key={version.id}
            className={cn(
              "w-full rounded-md border px-3 py-2 transition-colors",
              "hover:bg-muted/40 focus:outline-none focus:ring-2 focus:ring-ring",
              isSelected ? "bg-blue-50 border-blue-200" : "bg-white",
            )}
            aria-current={isSelected ? "true" : "false"}
            role="button"
            tabIndex={0}
            onClick={(e) => {
              if (deleteMutation.isPending) {
                e.preventDefault();
                return;
              }
              onSelectedVersionIdChange(version.id);
              if (!version.is_active) restoreMutation.mutate(version.id);
            }}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                if (deleteMutation.isPending) return;
                onSelectedVersionIdChange(version.id);
                if (!version.is_active) restoreMutation.mutate(version.id);
              }
            }}
          >
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium">
                    v{version.version_number}
                  </span>
                  {version.is_active && (
                    <Badge variant="outline" className="text-[9px] px-1.5">
                      Active
                    </Badge>
                  )}
                </div>
                <div className="text-xs text-muted-foreground truncate">
                  {version.label || formatFeedbackDate(version.created_at)}
                </div>
              </div>

              <div className="flex items-center gap-1 shrink-0">
                <div className="text-xs text-muted-foreground">
                  {formatFeedbackDate(version.created_at)}
                </div>
                {isSelected && (
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="h-7 w-7 p-0 text-destructive hover:text-destructive"
                    onClick={(e) => {
                      e.preventDefault();
                      e.stopPropagation();
                      setDeleteTargetId(version.id);
                      setIsDeleteDialogOpen(true);
                    }}
                    disabled={deleteMutation.isPending}
                    title="Delete version"
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                )}
              </div>
            </div>
          </div>
        );
      })}
      </div>

      <DeleteConfirmationDialog
        open={isDeleteDialogOpen}
        onOpenChange={(open) => {
          setIsDeleteDialogOpen(open);
          if (!open) setDeleteTargetId(null);
        }}
        title="Delete version?"
        itemName={
          deleteTarget
            ? `v${deleteTarget.version_number}${
                deleteTarget.label ? ` — ${deleteTarget.label}` : ""
              }`
            : undefined
        }
        onConfirm={async () => {
          if (!deleteTargetId) return;
          await deleteMutation.mutateAsync(deleteTargetId);
          setIsDeleteDialogOpen(false);
          setDeleteTargetId(null);
        }}
        isDeleting={deleteMutation.isPending}
      />
    </>
  );
};

