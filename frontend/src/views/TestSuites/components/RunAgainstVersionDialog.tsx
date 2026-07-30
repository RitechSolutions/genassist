import React, { useEffect, useState } from "react";
import { Loader2, Play } from "lucide-react";

import { Button } from "@/components/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/select";
import { getWorkflowSummaries } from "@/services/workflows";
import { getAgentConfig } from "@/services/api";
import { WorkflowSummary } from "@/interfaces/workflow.interface";

interface RunAgainstVersionDialogProps {
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  /** Groups the saved versions to choose from. */
  agentId: string;
  /** The version the evaluation runs against by default. */
  currentWorkflowId?: string;
  /** Named once in the description instead of repeated per option. */
  workflowName?: string;
  /** Confirm label, e.g. "Run" or "Run all". */
  confirmLabel?: string;
  isStarting?: boolean;
  onRun: (targetWorkflowId: string) => void;
}

export const RunAgainstVersionDialog: React.FC<RunAgainstVersionDialogProps> = ({
  isOpen,
  onOpenChange,
  agentId,
  currentWorkflowId,
  workflowName,
  confirmLabel = "Run",
  isStarting = false,
  onRun,
}) => {
  const [versions, setVersions] = useState<WorkflowSummary[]>([]);
  const [isLoadingVersions, setIsLoadingVersions] = useState(false);
  const [hasLoadFailed, setHasLoadFailed] = useState(false);
  const [selectedWorkflowId, setSelectedWorkflowId] = useState<string>("");
  // The agent's live version — the pointer the builder marks Active, and what a
  // plain Run executes.
  const [activeWorkflowId, setActiveWorkflowId] = useState<string | null>(null);
  // Bumped to refetch on retry.
  const [loadAttempt, setLoadAttempt] = useState(0);

  useEffect(() => {
    if (!isOpen) return;
    // A response from a previous open (or another agent) must never overwrite
    // the current one.
    let isStale = false;
    const loadVersions = async () => {
      setIsLoadingVersions(true);
      setHasLoadFailed(false);
      try {
        // A missing agent must not hide the version list; it only costs the marker.
        const [rows, agent] = await Promise.all([
          getWorkflowSummaries(agentId),
          getAgentConfig(agentId).catch(() => null),
        ]);
        if (isStale) return;
        setVersions(rows ?? []);
        setActiveWorkflowId(agent?.workflow_id ?? null);
        // Preselect what a plain Run would execute: the active version, or the
        // evaluation's own when the workflow has no active version.
        setSelectedWorkflowId(agent?.workflow_id ?? currentWorkflowId ?? "");
      } catch {
        // Distinct from an empty list: the versions are unknown, not absent.
        if (!isStale) {
          setVersions([]);
          setHasLoadFailed(true);
        }
      } finally {
        if (!isStale) setIsLoadingVersions(false);
      }
    };
    void loadVersions();
    return () => {
      isStale = true;
    };
  }, [isOpen, agentId, currentWorkflowId, loadAttempt]);

  // Each saved version carries its own name, so it is what tells two versions
  // apart once a workflow has many of them. "current" marks the agent's live
  // version, matching the wording of the wizard's workflow picker.
  const versionLabel = (version: WorkflowSummary): string => {
    const suffix = version.id === activeWorkflowId ? " (current)" : "";
    if (!version.name?.trim()) return `v${version.version}${suffix}`;
    return `v${version.version} · ${version.name}${suffix}`;
  };

  const hasOtherVersions = versions.length > 1;
  const canRun = Boolean(selectedWorkflowId) && hasOtherVersions && !isStarting;

  return (
    <Dialog open={isOpen} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Run against a version</DialogTitle>
        </DialogHeader>
        <div className="mt-2 space-y-4">
          <p className="text-sm text-muted-foreground">
            Execute against another saved version of{" "}
            {workflowName ?? "this workflow"} — for example a draft you are
            still working on.
          </p>
          <div className="space-y-1.5">
            <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Version
            </div>
            {isLoadingVersions ? (
              <div className="flex h-10 items-center gap-2 text-sm text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" />
                Loading versions…
              </div>
            ) : hasLoadFailed ? (
              <div className="flex items-center gap-3">
                <p className="flex-1 text-xs text-destructive">
                  Couldn't load this workflow's versions.
                </p>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setLoadAttempt((attempt) => attempt + 1)}
                >
                  Retry
                </Button>
              </div>
            ) : (
              <Select
                value={selectedWorkflowId}
                onValueChange={setSelectedWorkflowId}
                disabled={!hasOtherVersions}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Choose a version" />
                </SelectTrigger>
                <SelectContent>
                  {versions.map((version) => (
                    <SelectItem key={version.id} value={version.id}>
                      {versionLabel(version)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
            {!isLoadingVersions && !hasLoadFailed && !hasOtherVersions && (
              <p className="text-xs text-muted-foreground">
                This workflow has only one saved version. Save another version in
                the workflow builder to run against it here.
              </p>
            )}
          </div>
        </div>
        <DialogFooter className="mt-6 gap-2 border-t pt-4">
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button disabled={!canRun} onClick={() => onRun(selectedWorkflowId)}>
            {isStarting ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Play className="mr-2 h-4 w-4" />
            )}
            {confirmLabel}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
