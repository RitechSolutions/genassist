import React, { useState, useEffect, useCallback } from "react";
import { createPortal } from "react-dom";
import { X } from "lucide-react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { EditorTab } from "./EditorTab";
import { VersionsTab } from "./VersionsTab";
import { GoldDatasetTab } from "./GoldDatasetTab";
import { EvaluateOptimizeTab } from "./EvaluateOptimizeTab";
import { Badge } from "@/components/badge";

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
  const [activeTab, setActiveTab] = useState("editor");
  const [localPrompt, setLocalPrompt] = useState(currentValue);

  const handleApplyPrompt = (newPrompt: string) => {
    setLocalPrompt(newPrompt);
    onPromptChange(newPrompt);
  };

  // Sync local prompt when dialog opens with new value
  useEffect(() => {
    if (isOpen) {
      setLocalPrompt(currentValue);
    }
  }, [isOpen, currentValue]);

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
        <div className="flex flex-col max-h-[90vh]">
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
            className="flex-1 flex flex-col overflow-hidden"
          >
            <div className="px-6">
              <TabsList className="grid w-full grid-cols-4">
                <TabsTrigger value="editor">Editor</TabsTrigger>
                <TabsTrigger value="versions">Versions</TabsTrigger>
                <TabsTrigger value="gold-dataset">Gold Dataset</TabsTrigger>
                <TabsTrigger value="evaluate">Evaluate & Optimize</TabsTrigger>
              </TabsList>
            </div>

            <div className="flex-1 overflow-y-auto px-6 pb-6">
              <TabsContent value="editor">
                <EditorTab
                  workflowId={workflowId}
                  nodeId={nodeId}
                  promptField={promptField}
                  value={localPrompt}
                  onChange={handleApplyPrompt}
                />
              </TabsContent>

              <TabsContent value="versions">
                <VersionsTab
                  workflowId={workflowId}
                  nodeId={nodeId}
                  promptField={promptField}
                  onRestore={handleApplyPrompt}
                />
              </TabsContent>

              <TabsContent value="gold-dataset">
                <GoldDatasetTab
                  workflowId={workflowId}
                  nodeId={nodeId}
                  promptField={promptField}
                />
              </TabsContent>

              <TabsContent value="evaluate">
                <EvaluateOptimizeTab
                  workflowId={workflowId}
                  nodeId={nodeId}
                  promptField={promptField}
                  currentPrompt={localPrompt}
                  onAcceptOptimized={handleApplyPrompt}
                  defaultProviderId={defaultProviderId}
                />
              </TabsContent>
            </div>
          </Tabs>
        </div>
      </div>
    </>,
    document.body,
  );
};
