import React, { useRef, useState, useEffect, useCallback } from "react";
import { Button } from "@/components/button";
import { Download, Upload, MoreVertical, Play } from "lucide-react";
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
import { useFeatureFlagVisible } from "@/components/featureFlag";
import { FeatureFlags } from "@/config/featureFlags";
import { useAudioProvidersEnabled } from "../../hooks/useAudioProviderConfig";
import { ReferenceCheck, checkReferences } from "../../utils/referenceTargets";
import { ReferenceKind, replaceReferences } from "../../utils/workflowReferences";
import { MissingReferencesDialog } from "../MissingReferencesDialog";

// What an upload takes from the file
type UploadedGraph = Pick<Workflow, "nodes" | "edges" | "executionState" | "testInput">;

const INVALID_FILE = "Failed to load graph configuration. Invalid file format.";

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
  const [pendingUpload, setPendingUpload] = useState<
    (ReferenceCheck & { uploaded: UploadedGraph }) | null
  >(null);
  // Uploads load after network checks, so they read the latest workflow from here.
  const workflowRef = useRef(workflow);
  workflowRef.current = workflow;
  // Bumped per picked file, so only the newest upload loads.
  const uploadRun = useRef(0);
  const fallbackChainsEnabled = useFeatureFlagVisible(
    FeatureFlags.LLM_SETTINGS.SHOW_FALLBACK_CHAINS
  );
  const audioProvidersEnabled = useAudioProvidersEnabled();

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

  // Sync workflow structure (nodes/edges) to context - needed for getAvailableDataForNode
  useEffect(() => {
    if (workflow.nodes && workflow.edges) {
      setWorkflowStructure(workflow.nodes, workflow.edges);
    }
  }, [workflow.nodes, workflow.edges, setWorkflowStructure]);

  // Load execution state if available
  useEffect(() => {
    if (workflow.executionState) {
      loadExecutionState(workflow.executionState);
    }
  }, [workflow.executionState, loadExecutionState]);

  // An upload belongs to the workflow it started on.
  useEffect(() => {
    setPendingUpload(null);
  }, [workflow.id]);

  // Handle save to server
  const handleSaveToServer = async (): Promise<boolean> => {
    if (!onSaveWorkflow || !workflow) return true;

    // If workflow has no ID, open agent form first
    if (!workflow.id) {
      setAgentFormOpen(true);
      return true;
    }

    try {
      setIsSaving(true);
      await onSaveWorkflow(workflow);
      return true;
    } catch {
      return false;
    } finally {
      setIsSaving(false);
    }
  };

  const handleNavigation = async () => {
    if (await handleSaveToServer()) blocker.proceed();
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

  const loadUploaded = (uploaded: UploadedGraph) => {
    try {
      onWorkflowLoaded({ ...workflowRef.current, ...uploaded });
    } catch {
      alert(INVALID_FILE);
    }
  };

  // Load graph from file
  const handleLoadFromFile = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    const run = ++uploadRun.current;
    const workflowId = workflowRef.current.id;
    const reader = new FileReader();
    reader.onload = async (e) => {
      try {
        const content = e.target?.result as string;
        const importedWorkflow = JSON.parse(content) as Workflow;

        const uploaded: UploadedGraph = {
          nodes: importedWorkflow.nodes,
          edges: importedWorkflow.edges,
          executionState: importedWorkflow.executionState,
          testInput: importedWorkflow.testInput,
        };
        // Ids from another environment don't resolve here, so offer replacements first.
        const skipKinds: ReferenceKind[] = [];
        if (!fallbackChainsEnabled) skipKinds.push("fallbackChain");
        if (!audioProvidersEnabled) skipKinds.push("audioProvider");
        const check = await checkReferences(uploaded.nodes ?? [], skipKinds);
        // A newer upload or another workflow took over meanwhile.
        if (run !== uploadRun.current || workflowRef.current.id !== workflowId) return;
        if (check.missing.length > 0) {
          setPendingUpload({ ...check, uploaded });
          return;
        }
        // Load nodes and edges
        loadUploaded(uploaded);
      } catch {
        if (run === uploadRun.current) alert(INVALID_FILE);
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
      <div className="flex gap-2 bg-background/80 backdrop-blur-sm rounded-full shadow-sm p-1 pr-3">
        {onSaveWorkflow && (
          <Button
            onClick={handleSaveToServer}
            size="sm"
            variant="outline"
            className={`flex items-center gap-1 rounded-full ${
              !hasUnsavedChanges ? "opacity-50 cursor-not-allowed" : ""
            }`}
            title={hasUnsavedChanges ? "Save changes" : "No changes to save"}
            disabled={!hasUnsavedChanges || isSaving}
          >
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
          <Play className="h-4 w-4" />
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
              <Download className="mr-2 h-4 w-4" />
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

      {pendingUpload && (
        <MissingReferencesDialog
          isOpen
          missing={pendingUpload.missing}
          targets={pendingUpload.targets}
          onCancel={() => setPendingUpload(null)}
          onUpload={(replacements) => {
            const { uploaded } = pendingUpload;
            setPendingUpload(null);
            loadUploaded({
              ...uploaded,
              nodes: replaceReferences(uploaded.nodes ?? [], replacements),
            });
          }}
        />
      )}
    </>
  );
};

export default BottomPanel;
