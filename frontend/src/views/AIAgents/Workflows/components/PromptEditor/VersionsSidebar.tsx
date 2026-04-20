import React, { useEffect } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { History } from "lucide-react";
import { Badge } from "@/components/badge";
import { cn } from "@/lib/utils";
import { listPromptVersions, restorePromptVersion } from "@/services/promptEditor";
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
    <div className="space-y-1">
      {versions.map((version) => {
        const isSelected =
          selectedVersionId === version.id ||
          (!selectedVersionId && version.is_active);

        return (
          <button
            key={version.id}
            type="button"
            className={cn(
              "w-full text-left rounded-md border px-3 py-2 transition-colors",
              "hover:bg-muted/40 focus:outline-none focus:ring-2 focus:ring-ring",
              isSelected ? "bg-blue-50 border-blue-200" : "bg-white",
            )}
            onClick={() => {
              onSelectedVersionIdChange(version.id);
              if (!version.is_active) {
                restoreMutation.mutate(version.id);
              }
            }}
            disabled={restoreMutation.isPending && selectedVersionId !== version.id}
            aria-current={isSelected ? "true" : "false"}
          >
            <div className="flex items-center justify-between gap-2">
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium">
                    v{version.version_number}
                  </span>
                  {version.is_active && (
                    <Badge variant="default" className="text-[10px] px-1.5">
                      Active
                    </Badge>
                  )}
                </div>
                <div className="text-xs text-muted-foreground truncate">
                  {version.label || formatFeedbackDate(version.created_at)}
                </div>
              </div>
              <div className="text-xs text-muted-foreground shrink-0">
                {formatFeedbackDate(version.created_at)}
              </div>
            </div>
          </button>
        );
      })}
    </div>
  );
};

