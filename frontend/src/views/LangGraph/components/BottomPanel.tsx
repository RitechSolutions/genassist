import React, { useRef, useState } from "react";
import { Button } from "@/components/button";
import { Save, Upload, FolderOpen, PlayCircle } from "lucide-react";
import { Panel } from "reactflow";
import { Node, Edge } from "reactflow";
import {Workflow } from "@/interfaces/workflow.interface";
import { createWorkflow, updateWorkflow } from "@/services/workflows";
import WorkflowManager from "./WorkflowManager";

interface BottomPanelProps {
  workflow: Workflow;
  onWorkflowLoaded: (workflow: Workflow) => void;
  onTestWorkflow: (workflow: Workflow) => void;
}

const BottomPanel: React.FC<BottomPanelProps> = ({
  workflow,
  onWorkflowLoaded,
  onTestWorkflow,
}) => {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [workflowManagerOpen, setWorkflowManagerOpen] = useState(false);

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
  // Save to server
//   const handleSaveWorkflow = async (name: string, description: string) => {
//     try {


//       if (gd.id) {
//         // Update workflow on server
//         await updateWorkflow(workflow.id, workflow);
//       } else {
//         // Create workflow on server
//         await createWorkflow(workflow);
//         });

//         console.log("Workflow saved successfully");
//       }
//     } catch (error) {
//       console.error("Error saving workflow:", error);
//       throw error; // Re-throw to propagate to WorkflowManager
//     }
  

//   function handleGraphDataLoaded(nodes: Node[], edges: Edge[]): void {
//     onGraphDataLoaded(nodes, edges);
//   }

  return (
    <>
      <Panel position="bottom-center" className="mb-4">
        <div className="flex gap-2 bg-white/80 backdrop-blur-sm rounded-md shadow-sm p-2">
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
          {/* <Button
            onClick={() => {
              setWorkflowManagerOpen(true);
            }}
            size="sm"
            variant="outline"
            className="flex items-center gap-1"
            title="Manage saved workflows"
          >
            <FolderOpen className="h-4 w-4" />
            Workflows
          </Button> */}
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
      </Panel>
      {/* <WorkflowManager
        isOpen={workflowManagerOpen}
        onClose={() => setWorkflowManagerOpen(false)}
        onLoad={handleGraphDataLoaded}
        onSave={handleSaveWorkflow}
        workflow={workflow}
      /> */}
    </>
  );
};

export default BottomPanel;
