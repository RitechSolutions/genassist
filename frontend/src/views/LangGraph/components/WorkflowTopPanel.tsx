import React, { useState, useEffect } from "react";
import { Button } from "@/components/button";
import {
  Save,
  Plus,
  FolderOpen,
  PlayCircle,
  Trash2,
  Edit2,
  X,
} from "lucide-react";
import { Workflow } from "@/interfaces/workflow.interface";
import { getAllWorkflows, deleteWorkflow } from "@/services/workflows";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Input } from "@/components/input";
import { Label } from "@/components/label";
import { createWorkflow, updateWorkflow } from "@/services/workflows";

interface WorkflowTopPanelProps {
  isOpen: boolean;
  onClose: () => void;
  currentWorkflow: Workflow;
  onWorkflowSelect: (workflow: Workflow) => void;
  onWorkflowSave: (workflow: Workflow) => void;
}

const WorkflowTopPanel: React.FC<WorkflowTopPanelProps> = ({
  isOpen,
  onClose,
  currentWorkflow,
  onWorkflowSelect,
  onWorkflowSave,
}) => {
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [loading, setLoading] = useState(false);
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [workflowName, setWorkflowName] = useState(currentWorkflow.name || "");
  const [workflowDescription, setWorkflowDescription] = useState(
    currentWorkflow.description || ""
  );
  const [error, setError] = useState<string | null>(null);
  const [selectedWorkflowId, setSelectedWorkflowId] = useState<string | null>(
    null
  );

  // Load workflows
  const loadWorkflows = async () => {
    setLoading(true);
    setError(null);
    try {
      const workflowList = await getAllWorkflows();
      setWorkflows(workflowList || []);
    } catch (err) {
      console.error("Error loading workflows:", err);
      setError("Failed to load workflows. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadWorkflows();
  }, []);

  // Handle save workflow
  const handleCreateWorkflow = async () => {
    if (!workflowName.trim()) {
      return;
    }

    setError(null);
    try {
      const workflowToSave = {
        ...currentWorkflow,
        name: workflowName,
        description: workflowDescription,
        version: "1.0",
      };
      console.log(workflowToSave);

      console.log("Updating workflow");

      console.log("Creating workflow");
      delete workflowToSave.id;
      await createWorkflow(workflowToSave);
      closeDialogs();

      loadWorkflows();
    } catch (err) {
      console.error("Error saving workflow:", err);
      setError("Failed to save workflow. Please try again.");
    }
  };
  const closeDialogs = () => {
    setCreateDialogOpen(false);
    setEditDialogOpen(false);
    // setWorkflowName("");
    // setWorkflowDescription("");
  };
  const handleUpdateWorkflow = async () => {
    if (!workflowName.trim() && !currentWorkflow.id) {
      return;
    }

    setError(null);
    try {
      const workflowToSave = {
        ...currentWorkflow,
        name: workflowName != "" ? workflowName : currentWorkflow.name,
        description:
          workflowDescription != "" ? workflowDescription : currentWorkflow.description,
        version: "1.0",
      };
      console.log(workflowToSave);

      await updateWorkflow(currentWorkflow.id, workflowToSave);
      closeDialogs();
      loadWorkflows();
    } catch (err) {
      console.error("Error saving workflow:", err);
      setError("Failed to save workflow. Please try again.");
    }
  };

  // Handle delete workflow
  const handleDeleteWorkflow = async (workflowId: string) => {
    try {
      await deleteWorkflow(workflowId);
      setWorkflows(workflows.filter((w) => w.id !== workflowId));
    } catch (err) {
      console.error("Error deleting workflow:", err);
      setError("Failed to delete workflow. Please try again.");
    }
  };

  // Format date
  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString();
  };

  return (
    <div
      className={`fixed top-0 right-0 h-full w-80 bg-white border-l shadow-lg transform transition-transform duration-200 ease-in-out ${
        isOpen ? "translate-x-0" : "translate-x-full"
      }`}
    >
      <div className="h-full flex flex-col">
        <div className="p-4 border-b">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold">Workflows</h2>
            <Button
              onClick={onClose}
              size="icon"
              variant="ghost"
              className="h-8 w-8"
            >
              <X className="h-4 w-4" />
            </Button>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-4">
          <div className="flex items-center space-x-2 mb-4">
            <Button
              onClick={() => {
                setWorkflowName(currentWorkflow.name || "");
                setWorkflowDescription(currentWorkflow.description || "");
                if (currentWorkflow.id) {
                  handleUpdateWorkflow();
                } else {
                  setCreateDialogOpen(true);
                }
              }}
              size="sm"
              variant="outline"
              className="flex items-center gap-1"
            >
              <Save className="h-4 w-4" />
              Save Current
            </Button>
            <Button
              onClick={() => {
                setWorkflowName("");
                setWorkflowDescription("");
                setCreateDialogOpen(true);
              }}
              size="sm"
              variant="outline"
              className="flex items-center gap-1"
            >
              <Plus className="h-4 w-4" />
              New
            </Button>
          </div>

          {error && (
            <div className="mb-4 bg-red-50 border border-red-200 text-red-600 p-2 rounded-md text-sm">
              {error}
            </div>
          )}

          <div className="space-y-2">
            {workflows.map((workflow) => (
              <div
                key={workflow.id}
                className={`flex items-center space-x-2 p-2 rounded-md border cursor-pointer ${
                  selectedWorkflowId === workflow.id
                    ? "bg-blue-50 border-blue-200"
                    : "hover:bg-gray-50"
                }`}
                onClick={() => {
                  setSelectedWorkflowId(workflow.id);
                  onWorkflowSelect(workflow);
                }}
              >
                <div className="flex-1 min-w-0">
                  <div className="font-medium truncate">{workflow.name}</div>
                  <div className="text-xs text-gray-500 truncate">
                    {workflow.description || "No description"}
                  </div>
                </div>
                <div className="flex items-center space-x-1">
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-6 w-6"
                    onClick={(e) => {
                      e.stopPropagation();
                      setWorkflowName(workflow.name);
                      setWorkflowDescription(workflow.description || "");
                      setEditDialogOpen(true);
                    }}
                  >
                    <Edit2 className="h-3 w-3" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-6 w-6 text-red-500 hover:text-red-700"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDeleteWorkflow(workflow.id);
                    }}
                  >
                    <Trash2 className="h-3 w-3" />
                  </Button>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Save Workflow Dialog */}
      <Dialog
        open={editDialogOpen || createDialogOpen}
        onOpenChange={(open) => {
          setCreateDialogOpen(open);
          setEditDialogOpen(open);
        }}
      >
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Save Workflow</DialogTitle>
          </DialogHeader>

          <div className="space-y-4 py-2">
            <div className="space-y-2">
              <Label htmlFor="name">Workflow Name</Label>
              <Input
                id="name"
                placeholder="My Workflow"
                value={workflowName}
                onChange={(e) => setWorkflowName(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="description">Description (Optional)</Label>
              <Input
                id="description"
                placeholder="Description of what this workflow does"
                value={workflowDescription}
                onChange={(e) => setWorkflowDescription(e.target.value)}
              />
            </div>
          </div>

          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setCreateDialogOpen(false);
                setEditDialogOpen(false);
              }}
            >
              Cancel
            </Button>
            <Button
              onClick={() => {
                if (editDialogOpen) {
                  handleUpdateWorkflow();
                } else {
                  handleCreateWorkflow();
                }
              }}
              disabled={!workflowName.trim()}
              className="flex items-center gap-2"
            >
              <Save className="h-4 w-4" />
              Save
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default WorkflowTopPanel;
