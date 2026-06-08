import React, { useEffect, useCallback, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight, Save, X } from "lucide-react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { EditorTab } from "./EditorTab";
import { VersionsSidebar } from "./VersionsSidebar";
import { GoldDatasetTab } from "./GoldDatasetTab";
import { Badge } from "@/components/badge";
import { Button } from "@/components/button";
import { RichInput } from "@/components/richInput";
import { createPromptVersion } from "@/services/promptEditor";
import { AxiosError } from "axios";

interface PromptEditorDialogProps {
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  workflowId: string;
  nodeId: string;
  promptField: string;
  currentValue: string;
  onPromptChange: (newValue: string) => void;
  defaultProviderId?: string;
}

export const PromptEditorDialog: React.FC<PromptEditorDialogProps> = ({
  isOpen,
  onOpenChange,
  workflowId,
  nodeId,
  promptField,
  currentValue,
  onPromptChange,
  defaultProviderId,
}) => {
  const queryClient = useQueryClient();
  const wasOpenRef = useRef(false);
  const [activeTab, setActiveTab] = useState("editor");
  const [localPrompt, setLocalPrompt] = useState(currentValue);
  const [selectedVersionId, setSelectedVersionId] = useState<string | null>(null);
  const [isVersionsPanelOpen, setIsVersionsPanelOpen] = useState(true);
  const [isSaveLabelOpen, setIsSaveLabelOpen] = useState(false);
  const [saveLabelDraft, setSaveLabelDraft] = useState("");
  const saveLabelInputRef = useRef<HTMLInputElement | null>(null);
  const [saveVersionStatus, setSaveVersionStatus] = useState<
    { type: "success" | "error"; message: string } | null
  >(null);

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
      if (!result) {
        throw new Error("Server returned empty response — check permissions.");
      }
      return result;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["promptVersions", workflowId, nodeId, promptField],
      });
      setSaveVersionStatus({ type: "success", message: "Version saved" });
    },
    onError: (err) => {
      const detail =
        err instanceof AxiosError
          ? (err.response?.data as { detail?: unknown } | undefined)?.detail
          : undefined;
      const detailStr = typeof detail === "string" ? detail : undefined;
      setSaveVersionStatus({
        type: "error",
        message: `Failed to save: ${
          detailStr || (err instanceof Error ? err.message : "Unknown error")
        }`,
      });
    },
  });

  const handleApplyPrompt = (newPrompt: string) => {
    setLocalPrompt(newPrompt);
    onPromptChange(newPrompt);
  };

  // Sync local prompt only when dialog opens.
  // (Avoid resetting selection while restoring versions inside the dialog.)
  useEffect(() => {
    if (isOpen && !wasOpenRef.current) {
      setLocalPrompt(currentValue);
      setSelectedVersionId(null);
      setIsVersionsPanelOpen(true);
      setSaveVersionStatus(null);
      setIsSaveLabelOpen(false);
      setSaveLabelDraft("");
    }
    wasOpenRef.current = isOpen;
  }, [isOpen, currentValue]);

  useEffect(() => {
    if (isSaveLabelOpen) {
      window.requestAnimationFrame(() => saveLabelInputRef.current?.focus());
    }
  }, [isSaveLabelOpen]);

  // Close on Escape
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onOpenChange(false);
      }
    },
    [onOpenChange],
  );

  useEffect(() => {
    if (isOpen) {
      document.addEventListener("keydown", handleKeyDown);
      return () => document.removeEventListener("keydown", handleKeyDown);
    }
  }, [isOpen, handleKeyDown]);

  if (!isOpen) return null;

  // Render via portal directly on body to avoid Radix Dialog nesting issues
  // (NodeConfigPanel is a Sheet which is also a Radix Dialog)
  return createPortal(
    <>
      {/* Backdrop — must sit below Select popover (z-[1400]) */}
      <div
        className="fixed inset-0 bg-black/50 backdrop-blur-sm animate-in fade-in-0"
        style={{ zIndex: 1300 }}
        onClick={() => onOpenChange(false)}
      />
      {/* Panel — above Sheet (1201) and Dialog (1301) but below Select popover (1400) */}
      <div
        className="fixed left-[50%] top-[50%] translate-x-[-50%] translate-y-[-50%] w-full max-w-5xl rounded-lg border border-gray-200 bg-white shadow-lg animate-in fade-in-0 zoom-in-95"
        style={{ zIndex: 1350 }}
      >
        <div className="flex flex-col h-[80vh] min-h-0">
          {/* Header */}
          <div className="flex flex-col space-y-1.5 px-6 pt-6 pb-2">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-lg font-semibold leading-none tracking-tight flex items-center gap-2">
                  Prompt Editor <Badge variant="default">Beta</Badge>
                </h2>
                <p className="text-sm text-gray-500 mt-1.5">
                  Edit, version, evaluate, and optimize your prompt
                </p>
              </div>
              <button
                onClick={() => onOpenChange(false)}
                className="rounded-sm opacity-70 ring-offset-white transition-opacity hover:opacity-100 focus:outline-none"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          </div>

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
                        workflowId={workflowId}
                        nodeId={nodeId}
                        promptField={promptField}
                        selectedVersionId={selectedVersionId}
                        onSelectedVersionIdChange={setSelectedVersionId}
                        onRestore={handleApplyPrompt}
                      />
                    </div>

                    <div className="sticky bottom-0 z-20 bg-white border-t pt-3 pb-2">
                      {saveVersionStatus && (
                        <div
                          className={`text-xs mb-2 rounded-md px-2 py-1 ${
                            saveVersionStatus.type === "error"
                              ? "text-destructive bg-destructive/10 border border-destructive/20"
                              : "text-green-700 bg-green-50 border border-green-200"
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
                            className="absolute left-0 right-0 -top-2 translate-y-[-100%] z-[70] rounded-md border bg-white shadow-lg p-3"
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
                                  const trimmed = saveLabelDraft.trim();
                                  saveVersionMutation.mutate({
                                    content: localPrompt,
                                    label: trimmed ? trimmed : undefined,
                                  });
                                  setIsSaveLabelOpen(false);
                                  setSaveLabelDraft("");
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
                                onClick={() => {
                                  const trimmed = saveLabelDraft.trim();
                                  saveVersionMutation.mutate({
                                    content: localPrompt,
                                    label: trimmed ? trimmed : undefined,
                                  });
                                  setIsSaveLabelOpen(false);
                                  setSaveLabelDraft("");
                                }}
                                disabled={saveVersionMutation.isPending}
                              >
                                Save
                              </Button>
                            </div>
                          </div>
                        </>
                      )}

                      <Button
                        className="w-full"
                        onClick={() => setIsSaveLabelOpen(true)}
                        disabled={!localPrompt.trim() || saveVersionMutation.isPending}
                      >
                        <Save className="h-4 w-4 mr-2" />
                        {saveVersionMutation.isPending ? "Saving..." : "Save Version"}
                      </Button>
                    </div>
                  </aside>
                ) : (
                  <div className="shrink-0">
                    <button
                      type="button"
                      onClick={() => setIsVersionsPanelOpen(true)}
                      className="h-full rounded-md border bg-white px-2 text-xs text-muted-foreground hover:text-foreground hover:bg-muted/30 transition-colors"
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
                    <EditorTab
                      workflowId={workflowId}
                      nodeId={nodeId}
                      promptField={promptField}
                      value={localPrompt}
                      onChange={handleApplyPrompt}
                      defaultProviderId={defaultProviderId}
                    />
                  </TabsContent>

                  <TabsContent value="gold-dataset" className="mt-0">
                    <GoldDatasetTab
                      workflowId={workflowId}
                      nodeId={nodeId}
                      promptField={promptField}
                    />
                  </TabsContent>

                </div>
              </div>
            </div>
          </Tabs>
        </div>
      </div>
    </>,
    document.body,
  );
};
