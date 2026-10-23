import React, { useEffect, useMemo, useState } from "react";
import type { ImperativePanelHandle } from "react-resizable-panels";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { AlertCircle, ChevronDown, ChevronLeft, ChevronRight, X } from "lucide-react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Dialog,
  DialogDescription,
  DialogOverlay,
  DialogPortal,
  DialogTitle,
} from "@/components/dialog";
import {
  ResizableHandle,
  ResizablePanel,
  ResizablePanelGroup,
} from "@/components/resizable";
import { DraftPane } from "./DraftPane";
import { MeasurementPane } from "./MeasurementPane";
import { measurementStatus } from "./measurementStatus";
import { VersionsSidebar } from "./VersionsSidebar";
import { VersionPreviewPanel } from "./VersionPreviewPanel";
import { GoldDatasetTab } from "./GoldDatasetTab";
import { Badge } from "@/components/badge";
import { TooltipProvider } from "@/components/RadixTooltip";
import { Button } from "@/components/button";
import {
  createPromptVersion,
  deletePromptVersion,
  linkGoldSuite,
} from "@/services/promptEditor";
import { extractErrorMessage } from "@/helpers/apiError";
import { cn } from "@/lib/utils";
import { usePermissions } from "@/context/PermissionContext";
import { useWorkflow } from "../../context/WorkflowContext";
import nodeRegistry from "../../registry/nodeRegistry";
import { promptEditorCapabilities } from "../../utils/promptEditorCapabilities";
import {
  HISTORY_ERROR_REASON,
  HISTORY_FORBIDDEN_REASON,
  saveGate,
  type HistoryState,
} from "../../utils/promptEditorGates";
import {
  findPromptVersion,
  isCurrentDraft as isDraftEqual,
} from "../../utils/promptEditorHistory";
import {
  promptHistoryKey,
  promptHistoryWorkflowKey,
  usePromptHistory,
} from "./usePromptHistory";
import { usePromptMeasurement } from "./usePromptMeasurement";

interface PromptEditorDialogProps {
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  workflowId: string;
  nodeId: string;
  nodeType: string;
  nodeLabel?: string;
  promptField: string;
  currentValue: string;
  onPromptChange: (newValue: string) => void;
  defaultProviderId?: string;
}

/** Mount only when open so query and state reset each time */
export const PromptEditorDialog: React.FC<PromptEditorDialogProps> = (props) => {
  if (!props.isOpen) return null;
  return <PromptEditorDialogContent {...props} />;
};

const PromptEditorDialogContent: React.FC<PromptEditorDialogProps> = ({
  onOpenChange,
  workflowId,
  nodeId,
  nodeType,
  nodeLabel,
  promptField,
  currentValue,
  onPromptChange,
  defaultProviderId,
}) => {
  const queryClient = useQueryClient();
  const permissions = usePermissions();
  const { workflow } = useWorkflow();
  const caps = useMemo(() => promptEditorCapabilities(permissions), [permissions]);

  const [activeTab, setActiveTab] = useState("editor");
  const [localPrompt, setLocalPrompt] = useState(currentValue);
  const [undoSnapshot, setUndoSnapshot] = useState<string | null>(null);
  const [selectedVersionId, setSelectedVersionId] = useState<string | null>(null);
  const [isVersionsPanelOpen, setIsVersionsPanelOpen] = useState(true);
  const [comparisonCollapsed, setComparisonCollapsed] = useState(false);
  const [comparisonPanel, setComparisonPanel] =
    useState<ImperativePanelHandle | null>(null);
  const [saveVersionStatus, setSaveVersionStatus] = useState<
    { type: "success" | "error"; message: string } | null
  >(null);
  const [copyError, setCopyError] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [linkError, setLinkError] = useState<string | null>(null);

  const historyQuery = usePromptHistory(workflowId, nodeId, promptField, nodeType);
  const { history } = historyQuery;

  const nodeKey = promptHistoryKey(workflowId, nodeId, promptField);
  const invalidateNodeHistory = () =>
    queryClient.invalidateQueries({ queryKey: nodeKey });
  // Legacy rows are shared across nodes, so writes must refresh all their histories
  const invalidateWorkflowHistory = () =>
    queryClient.invalidateQueries({
      queryKey: promptHistoryWorkflowKey(workflowId),
    });

  const versions = history?.versions ?? [];
  const legacy = history?.legacy_shared ?? null;
  const legacyVersions = legacy?.versions ?? [];

  const historyState: HistoryState = {
    status: historyQuery.isPending
      ? "pending"
      : historyQuery.isError
        ? "error"
        : historyQuery.isForbidden
          ? "forbidden"
          : "ready",
    nodeMissing: history?.node_missing ?? false,
    inlineCheckSupported: history?.inline_check_supported ?? false,
    unsupportedReason: history?.unsupported_reason ?? null,
    goldSuiteId: history?.gold_suite_id ?? null,
  };
  const historyReady = historyState.status === "ready";

  const selected = findPromptVersion(versions, legacyVersions, selectedVersionId);
  const selectedVersion = selected?.version ?? null;
  const isSelectedLegacy = selected?.isLegacy ?? false;

  const resolvedNodeLabel =
    nodeLabel?.trim() || nodeRegistry.getNodeType(nodeType)?.label || nodeType;
  const fieldLabel = history?.field_label ?? promptField;
  const subtitle = `${workflow?.name || "Workflow"} / ${resolvedNodeLabel} / ${fieldLabel}`;

  const commitDraft = (value: string) => {
    setLocalPrompt(value);
    onPromptChange(value);
  };

  const handleDraftEdit = (value: string) => {
    setUndoSnapshot(null);
    commitDraft(value);
  };

  const handleApplyVersion = (content: string) => {
    setUndoSnapshot(localPrompt);
    commitDraft(content);
  };

  // Clicking the previewed row again hides it. A collapsed comparison is not a
  // preview, so the row that opened it, opens it again rather than deselecting
  const handleVersionSelect = (id: string) => {
    const isDeselect = selectedVersionId === id && !comparisonCollapsed;
    setSelectedVersionId(isDeselect ? null : id);
    if (isDeselect) return;
    setActiveTab("editor");
    comparisonPanel?.expand();
  };

  const handleUndoApply = () => {
    if (undoSnapshot === null) return;
    commitDraft(undoSnapshot);
    setUndoSnapshot(null);
  };

  const measurement = usePromptMeasurement({
    workflowId,
    nodeId,
    promptField,
    draft: localPrompt,
    onAccepted: handleDraftEdit,
    historyState,
    caps,
    defaultProviderId,
  });

  const saveVersionMutation = useMutation({
    mutationFn: async ({
      content,
      label,
    }: {
      content: string;
      label: string | undefined;
    }) => {
      setSaveVersionStatus(null);
      const result = await createPromptVersion(workflowId, nodeId, promptField, {
        content,
        label,
      });
      if (!result) throw new Error("Not allowed to save a version");
      return result;
    },
    onSuccess: (created) => {
      invalidateNodeHistory();
      setSaveVersionStatus({
        type: "success",
        message: `Saved as v${created.version_number}`,
      });
    },
    onError: (err) => {
      setSaveVersionStatus({
        type: "error",
        message: extractErrorMessage(err, "Failed to save the version"),
      });
    },
  });

  const copyVersionMutation = useMutation({
    mutationFn: async (vars: {
      content: string;
      label: string | undefined;
      sourceVersionId: string;
    }) => {
      setCopyError(null);
      const result = await createPromptVersion(workflowId, nodeId, promptField, {
        content: vars.content,
        label: vars.label,
      });
      if (!result) throw new Error("Not allowed to save a version");
      return result;
    },
    // Follow the copy only if the source row is still previewed
    onSuccess: async (created, variables) => {
      await invalidateNodeHistory();
      setSelectedVersionId((currentId) =>
        currentId === variables.sourceVersionId ? created.id : currentId,
      );
    },
    onError: (err) =>
      setCopyError(extractErrorMessage(err, "Failed to copy the version")),
  });

  const deleteVersionMutation = useMutation({
    mutationFn: async (vars: { versionId: string; isLegacy: boolean }) => {
      setDeleteError(null);
      await deletePromptVersion(vars.versionId);
    },
    // Wait for delete before closing dialog
    onSuccess: async (_result, vars) => {
      await (vars.isLegacy
        ? invalidateWorkflowHistory()
        : invalidateNodeHistory());
      setSelectedVersionId((current) =>
        current === vars.versionId ? null : current,
      );
    },
    onError: (err) =>
      setDeleteError(extractErrorMessage(err, "Failed to delete the version")),
  });

  const linkLegacyDatasetMutation = useMutation({
    mutationFn: async (suiteId: string) => {
      setLinkError(null);
      const result = await linkGoldSuite(workflowId, nodeId, promptField, {
        suite_id: suiteId,
      });
      if (!result) throw new Error("Not allowed to link a gold dataset");
      return result;
    },
    onSuccess: () => invalidateWorkflowHistory(),
    onError: (err) =>
      setLinkError(extractErrorMessage(err, "Failed to link the gold dataset")),
  });

  const gate = saveGate(historyState, caps, localPrompt);
  const canSaveVersion = gate.enabled && !saveVersionMutation.isPending;

  const hasMeasurement = caps.canEvaluate || caps.canOptimize;
  const draftDefaultSize =
    100 - (isVersionsPanelOpen ? 20 : 0) - (hasMeasurement ? 36 : 0);
  const hasSelectedVersion = selectedVersion !== null;

  useEffect(() => {
    if (!comparisonPanel) return;
    if (hasSelectedVersion) comparisonPanel.expand();
    else comparisonPanel.collapse();
  }, [comparisonPanel, hasSelectedVersion]);

  const status = measurementStatus(measurement);
  const runAnnouncement = [
    measurement.error,
    measurement.successMessage,
    status.evaluate && `Evaluate: ${status.evaluate}`,
    status.optimize && `Optimize: ${status.optimize}`,
  ]
    .filter(Boolean)
    .join(". ");

  const banner = historyQuery.isPending
    ? null
    : historyQuery.isError
      ? extractErrorMessage(historyQuery.error, HISTORY_ERROR_REASON)
      : historyQuery.isForbidden
        ? HISTORY_FORBIDDEN_REASON
        : history?.node_missing
          ? "This node isn't in the saved workflow. If it was just added, save the workflow before saving prompt versions or running checks."
          : null;

  return (
    <TooltipProvider delayDuration={200}>
    <Dialog open onOpenChange={onOpenChange}>
      <DialogPortal>
        <DialogOverlay className="z-[1300] bg-black/50 backdrop-blur-sm" />
        <DialogPrimitive.Content className="fixed left-1/2 top-1/2 z-[1350] flex h-[90vh] max-h-[90vh] w-[95vw] max-w-[1800px] -translate-x-1/2 -translate-y-1/2 flex-col gap-0 overflow-hidden rounded-lg border border-border bg-card p-0 shadow-lg data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95">
          <div className="shrink-0 border-b px-6 py-3">
            <div className="flex items-center justify-between gap-3">
              <div className="min-w-0">
                <DialogTitle className="flex items-center gap-2">
                    Prompt Editor <Badge variant="default">Beta</Badge>
                  </DialogTitle>
                  <DialogDescription className="mt-1.5 truncate">
                    {subtitle}
                  </DialogDescription>
                </div>
              <DialogPrimitive.Close className="shrink-0 rounded-sm opacity-70 ring-offset-white transition-opacity hover:opacity-100 focus:outline-none">
                <X className="h-4 w-4" />
                <span className="sr-only">Close</span>
              </DialogPrimitive.Close>
            </div>
          </div>

          {banner && (
            <div className="shrink-0 px-6 pt-3">
                <div className="flex items-start gap-2 text-amber-700 dark:text-amber-400 text-sm bg-amber-50 dark:bg-amber-500/15 border border-amber-200 dark:border-amber-500/30 rounded-md px-3 py-2">
                  <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
                  <span>{banner}</span>
                  {historyQuery.isError && (
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      className="ml-auto shrink-0"
                      onClick={() => historyQuery.refetch()}
                    >
                      Retry
                    </Button>
                  )}
                </div>
              </div>
            )}

          <Tabs
            value={activeTab}
            onValueChange={setActiveTab}
            className="flex min-h-0 flex-1 flex-col overflow-hidden"
          >
              <div className="shrink-0 px-6 pt-3">
                <TabsList className="grid w-full grid-cols-2">
                  <TabsTrigger value="editor">Editor</TabsTrigger>
                  <TabsTrigger value="gold-dataset">Gold Dataset</TabsTrigger>
                </TabsList>
              </div>

              <div className="min-h-0 flex-1">
                <TabsContent
                  value="editor"
                  forceMount
                  hidden={activeTab !== "editor"}
                  className="mt-0 h-full min-h-0"
                >
                  <div className="flex h-full min-h-0">
                    {!isVersionsPanelOpen && (
                      <div className="shrink-0 p-2">
                        <button
                          type="button"
                          onClick={() => setIsVersionsPanelOpen(true)}
                          className="h-full rounded-md border bg-card px-2 text-xs text-muted-foreground transition-colors hover:bg-muted/30 hover:text-foreground"
                          aria-label="Show versions panel"
                          title="Show versions"
                        >
                          <div className="flex items-center gap-1 [writing-mode:vertical-rl] rotate-180">
                            <ChevronRight className="h-4 w-4" />
                            Versions
                          </div>
                        </button>
                      </div>
                    )}
                    <ResizablePanelGroup
                      direction="horizontal"
                      autoSaveId="prompt-editor-v1"
                      className="h-full"
                    >
                      {isVersionsPanelOpen && (
                      <ResizablePanel
                        id="versions"
                        order={1}
                        defaultSize={20}
                        minSize={14}
                        maxSize={30}
                      >
                        <div className="flex h-full flex-col overflow-hidden">
                          <div className="flex shrink-0 items-center justify-between border-b px-3 py-2">
                            <span className="text-sm font-medium">Versions</span>
                            <Button
                              type="button"
                              size="sm"
                              variant="ghost"
                              className="w-9 px-0"
                              onClick={() => setIsVersionsPanelOpen(false)}
                              aria-label="Hide versions panel"
                            >
                              <ChevronLeft className="h-4 w-4" />
                            </Button>
                          </div>
                          <div className="min-h-0 flex-1 overflow-y-auto p-3">
                            <VersionsSidebar
                              versions={versions}
                              legacy={legacy}
                              selectedVersionId={selectedVersion?.id ?? null}
                              onSelect={handleVersionSelect}
                              canEditPrompt={caps.canEditPrompt && historyReady}
                              currentGoldSuiteId={historyState.goldSuiteId}
                              onLinkLegacyDataset={() => {
                                if (legacy?.gold_suite_id)
                                  linkLegacyDatasetMutation.mutate(
                                    legacy.gold_suite_id,
                                  );
                              }}
                              linkPending={linkLegacyDatasetMutation.isPending}
                              linkError={linkError}
                              status={historyState.status}
                              onDelete={(versionId, isLegacy) =>
                                deleteVersionMutation.mutateAsync({
                                  versionId,
                                  isLegacy,
                                })
                              }
                              deletingVersionId={
                                deleteVersionMutation.isPending
                                  ? (deleteVersionMutation.variables?.versionId ??
                                    null)
                                  : null
                              }
                              deleteError={deleteError}
                            />
                          </div>
                        </div>
                      </ResizablePanel>
                      )}

                      {isVersionsPanelOpen && <ResizableHandle withHandle />}

                      <ResizablePanel
                        id="draft"
                        order={2}
                        defaultSize={draftDefaultSize}
                        minSize={32}
                      >
                        <ResizablePanelGroup
                          direction="vertical"
                          autoSaveId="prompt-editor-draft-v1"
                          className="h-full"
                        >
                          <ResizablePanel
                            id="draft-editor"
                            order={1}
                            defaultSize={60}
                            minSize={30}
                          >
                            <DraftPane
                              nodeId={nodeId}
                              fieldLabel={fieldLabel}
                              value={localPrompt}
                              onDraftEdit={handleDraftEdit}
                              canEditPrompt={caps.canEditPrompt}
                              save={{
                                gate,
                                enabled: canSaveVersion,
                                pending: saveVersionMutation.isPending,
                                status: saveVersionStatus,
                                submit: (label) =>
                                  saveVersionMutation.mutate({
                                    content: localPrompt,
                                    label,
                                  }),
                              }}
                            />
                          </ResizablePanel>

                          <ResizableHandle withHandle />

                          <ResizablePanel
                            id="draft-comparison"
                            order={2}
                            defaultSize={40}
                            minSize={20}
                            collapsible
                            collapsedSize={0}
                            ref={setComparisonPanel}
                            onCollapse={() => setComparisonCollapsed(true)}
                            onExpand={() => setComparisonCollapsed(false)}
                          >
                            <div
                              className={cn(
                                "h-full overflow-hidden border-t",
                                !comparisonCollapsed && "flex flex-col",
                              )}
                              hidden={comparisonCollapsed}
                            >
                              {selectedVersion ? (
                                <VersionPreviewPanel
                                  key={selectedVersion.id}
                                  version={selectedVersion}
                                  isLegacy={isSelectedLegacy}
                                  versions={versions}
                                  legacyVersions={legacyVersions}
                                  draft={localPrompt}
                                  isCurrentDraft={isDraftEqual(
                                    selectedVersion,
                                    localPrompt,
                                  )}
                                  canEdit={caps.canEditPrompt}
                                  canUndo={undoSnapshot !== null}
                                  nodeMissing={historyState.nodeMissing}
                                  historyReady={historyReady}
                                  onApply={() =>
                                    handleApplyVersion(selectedVersion.content)
                                  }
                                  onUndo={handleUndoApply}
                                  onCopy={() =>
                                    copyVersionMutation.mutate({
                                      content: selectedVersion.content,
                                      label: selectedVersion.label ?? undefined,
                                      sourceVersionId: selectedVersion.id,
                                    })
                                  }
                                  isCopying={copyVersionMutation.isPending}
                                  copyError={copyError}
                                  onCollapse={() =>
                                    comparisonPanel?.collapse()
                                  }
                                />
                              ) : (
                                <>
                                  <div className="flex shrink-0 items-center justify-between border-b px-3 py-2">
                                    <span className="text-sm font-medium">
                                      Comparison
                                    </span>
                                    <Button
                                      type="button"
                                      size="icon"
                                      variant="ghost"
                                      className="h-7 w-7"
                                      onClick={() =>
                                        comparisonPanel?.collapse()
                                      }
                                      aria-label="Collapse comparison"
                                    >
                                      <ChevronDown className="h-4 w-4" />
                                    </Button>
                                  </div>
                                  <div className="flex min-h-0 flex-1 items-center justify-center p-6 text-center text-sm text-muted-foreground">
                                    Select a version to compare with the draft.
                                  </div>
                                </>
                              )}
                            </div>
                          </ResizablePanel>
                        </ResizablePanelGroup>
                      </ResizablePanel>

                      {hasMeasurement && <ResizableHandle withHandle />}

                      {hasMeasurement && (
                        <ResizablePanel
                          id="measurement"
                          order={3}
                          defaultSize={36}
                          minSize={26}
                        >
                          <MeasurementPane caps={caps} measurement={measurement} />
                        </ResizablePanel>
                      )}
                    </ResizablePanelGroup>
                  </div>
                </TabsContent>

                <TabsContent
                  value="gold-dataset"
                  className="mt-0 h-full min-h-0 overflow-y-auto px-6 pb-6 pt-4"
                >
                      <GoldDatasetTab
                        workflowId={workflowId}
                        nodeId={nodeId}
                        promptField={promptField}
                        goldSuiteId={historyState.goldSuiteId}
                        nodeMissing={historyState.nodeMissing}
                        historyStatus={historyState.status}
                        caps={caps}
                        nodeLabel={resolvedNodeLabel}
                        fieldLabel={fieldLabel}
                      />
                </TabsContent>
              </div>
          </Tabs>

          <p className="sr-only" role="status" aria-live="polite">
            {runAnnouncement}
          </p>
        </DialogPrimitive.Content>
      </DialogPortal>
    </Dialog>
    </TooltipProvider>
  );
};
