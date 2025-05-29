import React, { useRef, useState, useEffect } from "react";
import { Button } from "@/components/button";
import { Save, Upload, FolderOpen, PlayCircle } from "lucide-react";
import { Panel } from "reactflow";
import { Node, Edge } from "reactflow";
import { Workflow } from "@/interfaces/workflow.interface";
import { createWorkflow, updateWorkflow } from "@/services/workflows";
import WorkflowManager from "./WorkflowManager";
import { Dialog, DialogContent } from "@/components/dialog";
import AgentForm from "@/views/AIAgents/components/AgentForm";

interface AgentFormData {
  id?: string;
  name: string;
  description: string;
  llm_provider_id: string;
  system_prompt: string;
  knowledge_base_ids: string[];
  tool_ids: string[];
  settings: Record<string, unknown>;
  is_active: boolean;
  email: string;
  welcome_message: string;
  possible_queries: string[];
  [key: string]: unknown;
}

interface BottomPanelProps {
  workflow: Workflow;
  onWorkflowLoaded: (workflow: Workflow) => void;
  onTestWorkflow: (workflow: Workflow) => void;
  onSaveWorkflow?: (workflow: Workflow) => Promise<void>;
}

const BottomPanel: React.FC<BottomPanelProps> = ({
  workflow,
  onWorkflowLoaded,
  onTestWorkflow,
  onSaveWorkflow,
}) => {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [workflowManagerOpen, setWorkflowManagerOpen] = useState(false);
  const [hasChanges, setHasChanges] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [lastSavedWorkflow, setLastSavedWorkflow] = useState<Workflow | null>(
    null
  );
  const [agentFormOpen, setAgentFormOpen] = useState(false);

  // Compare workflows ignoring UI state fields
  const compareWorkflows = (
    workflow1: Workflow,
    workflow2: Workflow
  ): boolean => {
    delete workflow1.created_at;
    delete workflow1.updated_at;

    delete workflow2.created_at;
    delete workflow2.updated_at;

    const cleanWorkflow1 = {
      ...workflow1,
      nodes: workflow1.nodes?.map((node) => {
        const { selected, dragging, ...rest } = node;
        return rest;
      }),
      edges: workflow1.edges?.map((edge) => {
        const { selected, ...rest } = edge;
        return rest;
      }),
    };
    console.log("cleanWorkflow1", cleanWorkflow1);

    const cleanWorkflow2 = {
      ...workflow2,
      nodes: workflow2.nodes?.map((node) => {
        const { selected, dragging, ...rest } = node;
        return rest;
      }),
      edges: workflow2.edges?.map((edge) => {
        const { selected, ...rest } = edge;
        return rest;
      }),
    };
    console.log("cleanWorkflow2", cleanWorkflow2);
    return JSON.stringify(cleanWorkflow1) !== JSON.stringify(cleanWorkflow2);
  };

  // Track changes to workflow
  useEffect(() => {
    if (!workflow) return;

    // Initialize lastSavedWorkflow if it's null
    if (!lastSavedWorkflow || !workflow || workflow.id !== lastSavedWorkflow.id) {
      setLastSavedWorkflow(workflow);
      setHasChanges(false);
      return;
    }
    console.log("lastSavedWorkflow", lastSavedWorkflow);
    console.log("workflow", workflow);

    // Compare current workflow with last saved version
    const hasWorkflowChanged = compareWorkflows(lastSavedWorkflow, workflow);
    console.log("hasWorkflowChanged", hasWorkflowChanged);
    setHasChanges(hasWorkflowChanged);
  }, [workflow]);

  

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
      onSaveWorkflow(workflow);
      setLastSavedWorkflow(workflow);
      setHasChanges(false);
    } catch (error) {
      console.error("Error saving workflow:", error);
    } finally {
      setIsSaving(false);
    }
  };

  const handleAgentFormSubmit = async (formData: AgentFormData) => {
    if (!onSaveWorkflow || !workflow) return;

    try {
      setIsSaving(true);
      const updatedWorkflow = {
        ...workflow,
        ...formData,
      };
      await onSaveWorkflow(updatedWorkflow);
      setLastSavedWorkflow(updatedWorkflow);
      setHasChanges(false);
      setAgentFormOpen(false);
    } catch (error) {
      console.error("Error saving workflow:", error);
    } finally {
      setIsSaving(false);
    }
  };

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
        const gd = JSON.parse(content) as Workflow;

        // Load nodes and edges
        onWorkflowLoaded(gd);
        setLastSavedWorkflow(gd);
        setHasChanges(false);

        console.log(
          `Loaded graph configuration (version: ${workflow.version}, saved: ${
            workflow.created_at || "unknown"
          })`
        );
      } catch (error) {
        console.error("Error loading graph configuration:", error);
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
      <div className="flex gap-2 bg-white/80 backdrop-blur-sm rounded-md shadow-sm p-2">
        {onSaveWorkflow && (
          <Button
            onClick={handleSaveToServer}
            size="sm"
            variant="outline"
            className={`flex items-center gap-1 ${
              hasChanges
                ? "text-blue-600 border-blue-200 hover:bg-blue-50"
                : "opacity-50 cursor-not-allowed"
            }`}
            title={hasChanges ? "Save changes" : "No changes to save"}
            disabled={!hasChanges || isSaving}
          >
            <Save className={`h-4 w-4 ${isSaving ? "animate-spin" : ""}`} />
            {isSaving ? "Saving..." : "Save"}
          </Button>
        )}
        <Button
          onClick={handleSaveToFile}
          size="sm"
          variant="outline"
          className="flex items-center gap-1"
          title="Download as JSON file"
        >
          <Save className="h-4 w-4" />
          Download
        </Button>
        <Button
          onClick={triggerFileUpload}
          size="sm"
          variant="outline"
          className="flex items-center gap-1"
          title="Upload from JSON file"
        >
          <Upload className="h-4 w-4" />
          Upload
        </Button>
        <Button
          onClick={handleTestCurrentGraph}
          size="sm"
          variant="outline"
          className="flex items-center gap-1 text-green-600 border-green-200 hover:bg-green-50"
          title="Test current graph"
          disabled={workflow?.nodes?.length === 0}
        >
          <PlayCircle className="h-4 w-4" />
          Test
        </Button>
        <input
          type="file"
          ref={fileInputRef}
          onChange={handleLoadFromFile}
          accept=".json"
          className="hidden"
        />
      </div>
    </>
  );
};

export default BottomPanel;
