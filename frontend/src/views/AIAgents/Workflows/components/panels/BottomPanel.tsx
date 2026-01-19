import React, { useRef, useState, useEffect, useCallback } from "react";
import { Button } from "@/components/button";
import { Save, Upload, PlayCircle, MoreVertical } from "lucide-react";
import { useBlocker } from "react-router-dom";
import { Workflow } from "@/interfaces/workflow.interface";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import {
  useWorkflowExecution,
  WorkflowExecutionState,
} from "../../context/WorkflowExecutionContext";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/dropdown-menu";

interface BottomPanelProps {
  workflow: Workflow;
  hasUnsavedChanges: boolean;
  onWorkflowLoaded: (workflow: Workflow) => void;
  onTestWorkflow: (workflow: Workflow) => void;
  onSaveWorkflow?: (workflow: Workflow) => Promise<void>;
  onExecutionStateChange?: (executionState: WorkflowExecutionState) => void;
}

const BottomPanel: React.FC<BottomPanelProps> = ({
  workflow,
  hasUnsavedChanges,
  onWorkflowLoaded,
  onTestWorkflow,
  onSaveWorkflow,
  onExecutionStateChange,
}) => {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [agentFormOpen, setAgentFormOpen] = useState(false);
  const [isDialogOpen, setIsDialogOpen] = useState(false);

  const {
    state: executionState,
    loadExecutionState,
    setWorkflowStructure,
  } = useWorkflowExecution();

  useEffect(() => {
    if (onExecutionStateChange) {
      onExecutionStateChange(executionState);
    }
  }, [executionState, onExecutionStateChange]);

  useEffect(() => {
    if (workflow.executionState && workflow.nodes && workflow.edges) {
      setWorkflowStructure(workflow.nodes, workflow.edges);
      loadExecutionState(workflow.executionState);
    }
  }, [workflow.nodes, workflow.edges]);

  // Handle save to server
  const handleSaveToServer = async () => {
    if (!onSaveWorkflow || !workflow) return;

    // If workflow has no ID, open agent form first
    if (!workflow.id) {
      setAgentFormOpen(true);
      return;
    }

    try {
      setIsSaving(true);
      await onSaveWorkflow(workflow);
    } catch (error) {
      // ignore
    } finally {
      setIsSaving(false);
    }
  };

  const handleNavigation = async () => {
    await handleSaveToServer();
    blocker.proceed();
  };

  const handleDiscard = () => {
    blocker.proceed();
  };

  const blocker = useBlocker(
    useCallback(
      ({ currentLocation, nextLocation }) =>
        hasUnsavedChanges && currentLocation.pathname !== nextLocation.pathname,
      [hasUnsavedChanges]
    )
  );

  useEffect(() => {
    if (blocker.state === "blocked") {
      setIsDialogOpen(true);
    }
  }, [blocker]);

  // Save graph to local file
  const handleSaveToFile = () => {
    // Convert to JSON string
    const jsonData = JSON.stringify(workflow, null, 2);

    // Create blob and download link
    const blob = new Blob([jsonData], { type: "application/json" });
    const url = URL.createObjectURL(blob);

    // Create download link and trigger click
    const a = document.createElement("a");
    a.href = url;
    a.download = `langgraph-config-${new Date()
      .toISOString()
      .slice(0, 10)}.json`;
    document.body.appendChild(a);
    a.click();

    // Clean up
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  // Load graph from file
  const handleLoadFromFile = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const content = e.target?.result as string;
        const importedWorkflow = JSON.parse(content) as Workflow;

        const gd: Workflow = {
          ...workflow,
          nodes: importedWorkflow.nodes,
          edges: importedWorkflow.edges,
          executionState: importedWorkflow.executionState,
          testInput: importedWorkflow.testInput,
        };
        // Load nodes and edges
        onWorkflowLoaded(gd);
      } catch (error) {
        alert("Failed to load graph configuration. Invalid file format.");
      }
    };

    reader.readAsText(file);

    // Reset file input
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const triggerFileUpload = () => {
    if (fileInputRef.current) {
      fileInputRef.current.click();
    }
  };

  // Handle test current graph
  const handleTestCurrentGraph = () => {
    if (workflow?.nodes?.length === 0) {
      alert("Cannot test an empty graph. Add some nodes first.");
      return;
    }
    onTestWorkflow(workflow);
  };

  return (
    <>
      <div className="flex gap-2 bg-white/80 backdrop-blur-sm rounded-full shadow-sm p-1">
        {onSaveWorkflow && (
          <Button
            onClick={handleSaveToServer}
            size="sm"
            variant="outline"
            className={`flex items-center gap-1 rounded-full ${
              hasUnsavedChanges
                ? "text-blue-600 border-blue-200 hover:bg-blue-50"
                : "opacity-50 cursor-not-allowed"
            }`}
            title={hasUnsavedChanges ? "Save changes" : "No changes to save"}
            disabled={!hasUnsavedChanges || isSaving}
          >
            <Save className={`h-4 w-4 ${isSaving ? "animate-spin" : ""}`} />
            {isSaving ? "Saving..." : "Save"}
          </Button>
        )}
        <Button
          onClick={handleTestCurrentGraph}
          size="sm"
          className="flex items-center gap-1 rounded-full bg-blue-600 hover:bg-blue-700 text-white"
          title="Test current graph"
          disabled={
            !workflow?.nodes?.some((node) => node.type === "chatInputNode")
          }
        >
          <PlayCircle className="h-4 w-4" />
          Test
        </Button>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              size="sm"
              variant="ghost"
              className="h-auto p-0 hover:bg-transparent"
            >
              <MoreVertical className="h-4 w-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem onClick={handleSaveToFile}>
              <Save className="mr-2 h-4 w-4" />
              <span>Download</span>
            </DropdownMenuItem>
            <DropdownMenuItem onClick={triggerFileUpload}>
              <Upload className="mr-2 h-4 w-4" />
              <span>Upload</span>
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
        <input
          type="file"
          ref={fileInputRef}
          onChange={handleLoadFromFile}
          accept=".json"
          className="hidden"
        />
      </div>

      <ConfirmDialog
        isOpen={isDialogOpen}
        onOpenChange={setIsDialogOpen}
        onConfirm={handleNavigation}
        isInProgress={isSaving}
        primaryButtonText="Save"
        secondaryButtonText="Discard"
        onCancel={handleDiscard}
        title="You have unsaved changes!"
        description="Would you like to save or discard them?"
      />
    </>
  );
};

export default BottomPanel;
