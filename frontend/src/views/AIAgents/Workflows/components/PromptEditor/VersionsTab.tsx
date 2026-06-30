import React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { History, RotateCcw, Trash2 } from "lucide-react";
import { Button } from "@/components/button";
import { Badge } from "@/components/badge";
import {
  deletePromptVersion,
  listPromptVersions,
  restorePromptVersion,
} from "@/services/promptEditor";
import type { PromptVersion } from "@/interfaces/promptEditor.interface";

interface VersionsTabProps {
  workflowId: string;
  nodeId: string;
  promptField: string;
  onRestore: (content: string) => void;
}

export const VersionsTab: React.FC<VersionsTabProps> = ({
  workflowId,
  nodeId,
  promptField,
  onRestore,
}) => {
  const queryClient = useQueryClient();
  const queryKey = ["promptVersions", workflowId, nodeId, promptField];

  const { data: versions = [], isLoading } = useQuery({
    queryKey,
    queryFn: () => listPromptVersions(workflowId, nodeId, promptField),
    select: (data) => (data ?? []) as PromptVersion[],
  });

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

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12 text-muted-foreground">
        Loading versions...
      </div>
    );
  }

  if (versions.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-muted-foreground gap-2">
        <History className="h-8 w-8" />
        <p>No versions saved yet</p>
        <p className="text-xs">Save a version from the Editor tab to start tracking changes</p>
      </div>
    );
  }

  return (
    <div className="space-y-2 pt-4">
      {versions.map((version) => (
        <div
          key={version.id}
          className={`flex items-start gap-3 rounded-lg border p-3 ${
            version.is_active ? "border-blue-200 bg-blue-50" : ""
          }`}
        >
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <span className="font-medium text-sm">v{version.version_number}</span>
              {version.label && (
                <span className="text-sm text-muted-foreground truncate">
                  {version.label}
                </span>
              )}
              {version.is_active && (
                <Badge variant="secondary" className="text-xs">
                  Active
                </Badge>
              )}
            </div>
            <p className="text-xs text-muted-foreground line-clamp-2 font-mono">
              {version.content}
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              {new Date(version.created_at).toLocaleString()}
            </p>
          </div>
          <div className="flex gap-1 shrink-0">
            <Button
              variant="ghost"
              size="sm"
              className="h-8 w-8 p-0"
              onClick={() => restoreMutation.mutate(version.id)}
              disabled={version.is_active || restoreMutation.isPending}
              title="Restore this version"
            >
              <RotateCcw className="h-4 w-4" />
            </Button>
            <Button
              variant="ghost"
              size="sm"
              className="h-8 w-8 p-0 text-destructive hover:text-destructive"
              onClick={() => deleteMutation.mutate(version.id)}
              disabled={deleteMutation.isPending}
              title="Delete this version"
            >
              <Trash2 className="h-4 w-4" />
            </Button>
          </div>
        </div>
      ))}
    </div>
  );
};
