import React, { useEffect, useMemo, useRef, useState } from "react";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { AlertCircle, ChevronLeft, ChevronRight, Save, X } from "lucide-react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Dialog,
  DialogDescription,
  DialogOverlay,
  DialogPortal,
  DialogTitle,
} from "@/components/dialog";
import { EditorTab } from "./EditorTab";
import { VersionsSidebar } from "./VersionsSidebar";
import { VersionPreviewPanel } from "./VersionPreviewPanel";
import { GoldDatasetTab } from "./GoldDatasetTab";
import { GateTooltip } from "./GateTooltip";
import { Badge } from "@/components/badge";
import { TooltipProvider } from "@/components/RadixTooltip";
import { Button } from "@/components/button";
import { RichInput } from "@/components/richInput";
import {
  createPromptVersion,
  deletePromptVersion,
  linkGoldSuite,
} from "@/services/promptEditor";
import { extractErrorMessage } from "@/helpers/apiError";
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
  const [isSaveLabelOpen, setIsSaveLabelOpen] = useState(false);
  const [saveLabelDraft, setSaveLabelDraft] = useState("");
  const saveLabelInputRef = useRef<HTMLInputElement | null>(null);
  const [saveVersionStatus, setSaveVersionStatus] = useState<
    { type: "success" | "error"; message: string } | null
  >(null);
  const [copyError, setCopyError] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [linkError, setLinkError] = useState<string | null>(null);

  // Guard against stale async overwrites
  const latestDraftRef = useRef(localPrompt);
  latestDraftRef.current = localPrompt;

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

  // Clicking the previewed row again closes the panel; a new pick reveals it on the Editor tab
  const handleVersionSelect = (id: string) => {
    const isDeselect = selectedVersionId === id;
    setSelectedVersionId(isDeselect ? null : id);
    if (!isDeselect) setActiveTab("editor");
  };

  const handleUndoApply = () => {
    if (undoSnapshot === null) return;
    commitDraft(undoSnapshot);
    setUndoSnapshot(null);
  };

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

  useEffect(() => {
    if (isSaveLabelOpen) {
      window.requestAnimationFrame(() => saveLabelInputRef.current?.focus());
    }
  }, [isSaveLabelOpen]);

  const gate = saveGate(historyState, caps, localPrompt);
  const canSaveVersion = gate.enabled && !saveVersionMutation.isPending;

  const submitSaveVersion = () => {
    if (!canSaveVersion) return;
    const trimmed = saveLabelDraft.trim();
    saveVersionMutation.mutate({
      content: localPrompt,
      label: trimmed ? trimmed : undefined,
    });
    setIsSaveLabelOpen(false);
    setSaveLabelDraft("");
  };

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
        <DialogPrimitive.Content
          className="fixed left-1/2 top-1/2 z-[1350] w-full max-w-5xl -translate-x-1/2 -translate-y-1/2 rounded-lg border border-border bg-card shadow-lg data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95"
          onEscapeKeyDown={(e) => {
            if (isSaveLabelOpen) {
              e.preventDefault();
              setIsSaveLabelOpen(false);
            }
          }}
        >
          <div className="flex flex-col h-[80vh] min-h-0">
            <div className="flex flex-col space-y-1.5 px-6 pt-6 pb-2">
              <div className="flex items-center justify-between">
                <div className="min-w-0">
                  <DialogTitle className="flex items-center gap-2">
                    Prompt Editor <Badge variant="default">Beta</Badge>
                  </DialogTitle>
                  <DialogDescription className="mt-1.5 truncate">
                    {subtitle}
                  </DialogDescription>
                </div>
                <DialogPrimitive.Close className="rounded-sm opacity-70 ring-offset-white transition-opacity hover:opacity-100 focus:outline-none">
                  <X className="h-4 w-4" />
                  <span className="sr-only">Close</span>
                </DialogPrimitive.Close>
              </div>
            </div>

            {banner && (
              <div className="px-6 pb-1">
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
              className="flex-1 flex flex-col overflow-hidden min-h-0"
            >
              <div className="px-6">
                <TabsList className="grid w-full grid-cols-2">
                  <TabsTrigger value="editor">Editor</TabsTrigger>
                  <TabsTrigger value="gold-dataset">Gold Dataset</TabsTrigger>
                </TabsList>
              </div>

              <div className="flex-1 min-h-0 overflow-hidden px-6 pb-6 pt-4">
                <div className="flex h-full min-h-0 gap-4">
                  {isVersionsPanelOpen ? (
                    <aside className="w-64 shrink-0 px-2 pr-4 border-r min-h-0 flex flex-col">
                      <div className="flex items-center justify-between mb-2">
                        <div className="text-xs font-medium text-muted-foreground">
                          Versions
                        </div>
                        <button
                          type="button"
                          onClick={() => setIsVersionsPanelOpen(false)}
                          className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
                          aria-label="Hide versions panel"
                        >
                          <ChevronLeft className="h-4 w-4" />
                          Hide
                        </button>
                      </div>
                      <div className="flex-1 min-h-0 overflow-y-auto pb-3">
                        <VersionsSidebar
                          versions={versions}
                          legacy={legacy}
                          selectedVersionId={selectedVersion?.id ?? null}
                          onSelect={handleVersionSelect}
                          canEditPrompt={caps.canEditPrompt && historyReady}
                          currentGoldSuiteId={historyState.goldSuiteId}
                          onLinkLegacyDataset={() => {
                            if (legacy?.gold_suite_id)
                              linkLegacyDatasetMutation.mutate(legacy.gold_suite_id);
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
                              ? (deleteVersionMutation.variables?.versionId ?? null)
                              : null
                          }
                          deleteError={deleteError}
                        />
                      </div>

                      <div className="sticky bottom-0 z-20 bg-card border-t pt-3 pb-2">
                        {saveVersionStatus && (
                          <div
                            className={`text-xs mb-2 rounded-md px-2 py-1 ${
                              saveVersionStatus.type === "error"
                                ? "text-destructive bg-destructive/10 border border-destructive/20"
                                : "text-green-700 dark:text-green-400 bg-green-50 dark:bg-green-500/15 border border-green-200 dark:border-green-500/30"
                            }`}
                          >
                            {saveVersionStatus.message}
                          </div>
                        )}

                        {isSaveLabelOpen && (
                          <>
                            <button
                              type="button"
                              className="fixed inset-0 cursor-default"
                              style={{ zIndex: 60 }}
                              aria-label="Close label prompt"
                              onClick={() => setIsSaveLabelOpen(false)}
                            />
                            <div
                              className="absolute left-0 right-0 -top-2 translate-y-[-100%] z-[70] rounded-md border bg-card shadow-lg p-3"
                              role="dialog"
                              aria-label="Save version label"
                            >
                              <div className="text-xs font-medium mb-2">
                                Version label (optional)
                              </div>
                              <RichInput
                                ref={saveLabelInputRef}
                                value={saveLabelDraft}
                                onChange={(e) => setSaveLabelDraft(e.target.value)}
                                placeholder="e.g., Added tone instructions"
                                maxLength={200}
                                onKeyDown={(e) => {
                                  if (e.key === "Escape") {
                                    setIsSaveLabelOpen(false);
                                  }
                                  if (e.key === "Enter") {
                                    submitSaveVersion();
                                  }
                                }}
                              />
                              <div className="flex justify-end gap-2 mt-3">
                                <Button
                                  type="button"
                                  size="sm"
                                  variant="ghost"
                                  onClick={() => setIsSaveLabelOpen(false)}
                                >
                                  Cancel
                                </Button>
                                <Button
                                  type="button"
                                  size="sm"
                                  onClick={submitSaveVersion}
                                  disabled={!canSaveVersion}
                                >
                                  Save
                                </Button>
                              </div>
                            </div>
                          </>
                        )}

                        {caps.canEditPrompt && (
                          <GateTooltip reason={gate.reason}>
                            <Button
                              className="w-full"
                              onClick={() => setIsSaveLabelOpen(true)}
                              disabled={!canSaveVersion}
                            >
                              <Save className="h-4 w-4 mr-2" />
                              {saveVersionMutation.isPending
                                ? "Saving..."
                                : "Save Version"}
                            </Button>
                          </GateTooltip>
                        )}
                      </div>
                    </aside>
                  ) : (
                    <div className="shrink-0">
                      <button
                        type="button"
                        onClick={() => setIsVersionsPanelOpen(true)}
                        className="h-full rounded-md border bg-card px-2 text-xs text-muted-foreground hover:text-foreground hover:bg-muted/30 transition-colors"
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

                  <div className="flex-1 min-h-0 overflow-y-auto">
                    <TabsContent value="editor" className="mt-0">
                      {selectedVersion && (
                        <VersionPreviewPanel
                          key={selectedVersion.id}
                          version={selectedVersion}
                          isLegacy={isSelectedLegacy}
                          versions={versions}
                          legacyVersions={legacyVersions}
                          draft={localPrompt}
                          isCurrentDraft={isDraftEqual(selectedVersion, localPrompt)}
                          canEdit={caps.canEditPrompt}
                          canUndo={undoSnapshot !== null}
                          nodeMissing={historyState.nodeMissing}
                          historyReady={historyReady}
                          onApply={() => handleApplyVersion(selectedVersion.content)}
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
                        />
                      )}

                      <EditorTab
                        workflowId={workflowId}
                        nodeId={nodeId}
                        promptField={promptField}
                        value={localPrompt}
                        onDraftEdit={handleDraftEdit}
                        onAccepted={handleDraftEdit}
                        latestDraftRef={latestDraftRef}
                        fieldLabel={fieldLabel}
                        historyState={historyState}
                        caps={caps}
                        defaultProviderId={defaultProviderId}
                      />
                    </TabsContent>

                    <TabsContent value="gold-dataset" className="mt-0">
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
                </div>
              </div>
            </Tabs>
          </div>
        </DialogPrimitive.Content>
      </DialogPortal>
    </Dialog>
    </TooltipProvider>
  );
};
