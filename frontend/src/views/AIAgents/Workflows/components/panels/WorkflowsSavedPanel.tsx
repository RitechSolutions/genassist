import React, { useState, useEffect } from "react";
import { Button } from "@/components/button";
import { Save, Plus, Trash2, Edit, Power, MoreVertical } from "lucide-react";
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
import { ConfirmDialog } from "@/components/ConfirmDialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
  DropdownMenuSeparator,
} from "@/components/dropdown-menu";
import { calculateNextVersion, findPreviousVersion, isVersionDuplicate } from "../../utils/helpers";

interface WorkflowsSavedPanelProps {
  isOpen: boolean;
  onClose: () => void;
  agentId: string;
  activeWorkflowId: string;
  currentWorkflow: Workflow;
  onWorkflowSelect: (workflow: Workflow) => void;
  onActiveWorkflowChange: (workflow: Workflow) => void;
  refreshKey: number;
  hasUnsavedChanges: boolean;
  onSaveWorkflow: () => Promise<void>;
}

const WorkflowsSavedPanel: React.FC<WorkflowsSavedPanelProps> = ({
  isOpen,
  onClose,
  agentId,
  activeWorkflowId,
  currentWorkflow,
  onWorkflowSelect,
  onActiveWorkflowChange,
  refreshKey,
  hasUnsavedChanges,
  onSaveWorkflow,
}) => {
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [loading, setLoading] = useState(false);
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [workflowName, setWorkflowName] = useState(currentWorkflow.name || "");
  const [workflowVersion, setWorkflowVersion] = useState(
    currentWorkflow.version || ""
  );
  const [workflowDescription, setWorkflowDescription] = useState(
    currentWorkflow.description || ""
  );
  const [error, setError] = useState<string | null>(null);
  const [versionError, setVersionError] = useState<string | null>(null);
  const [selectedWorkflowId, setSelectedWorkflowId] = useState<string | null>(
    null
  );

  const [workflowToActivate, setWorkflowToActivate] = useState<Workflow | null>(
    null
  );
  const [isActivateDialogOpen, setIsActivateDialogOpen] = useState(false);
  const [isActivating, setIsActivating] = useState(false);

  const [workflowToDelete, setWorkflowToDelete] = useState<Workflow | null>(
    null
  );
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  const [isUnsavedChangesDialogOpen, setIsUnsavedChangesDialogOpen] =
    useState(false);
  const [workflowToSelect, setWorkflowToSelect] = useState<Workflow | null>(
    null
  );
  const [isSwitching, setIsSwitching] = useState(false);

  // Load workflows
  const loadWorkflows = async () => {
    setLoading(true);
    setError(null);
    try {
      let workflowList = await getAllWorkflows();
      workflowList = workflowList.filter(
        (workflow) => workflow["agent_id"] === agentId
      );
      workflowList.sort((a, b) => {
        const dateA = new Date(a.created_at).getTime();
        const dateB = new Date(b.created_at).getTime();
        return dateB - dateA;
      });
      setWorkflows(workflowList || []);
    } catch (err) {
      setError("Failed to load workflows. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen && agentId) {
      loadWorkflows();
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen, agentId, refreshKey]);

  useEffect(() => {
    if (currentWorkflow?.id && currentWorkflow.id !== selectedWorkflowId) {
      setSelectedWorkflowId(currentWorkflow.id);
      onWorkflowSelect(currentWorkflow);
    }
  }, [currentWorkflow, currentWorkflow.id, onWorkflowSelect, selectedWorkflowId]);

  // Handle save workflow
  const handleCreateWorkflow = async () => {
    if (!workflowName.trim()) {
      return;
    }

    // Check for duplicate version
    if (isVersionDuplicate(workflows, workflowVersion)) {
      setVersionError(`Version "${workflowVersion}" already exists. Please choose a different version number.`);
      return;
    }

    setError(null);
    setVersionError(null);
    try {
      const workflowToSave = {
        ...currentWorkflow,
        name: workflowName,
        description: workflowDescription,
        version: workflowVersion,
      };
      delete workflowToSave.id;
      await createWorkflow(workflowToSave);
      closeDialogs();

      loadWorkflows();
    } catch (err) {
      setError("Failed to save workflow. Please try again.");
    }
  };

  const handleWorkflowSelect = (workflow: Workflow) => {
    if (workflow.id === selectedWorkflowId) return;

    if (hasUnsavedChanges) {
      setWorkflowToSelect(workflow);
      setIsUnsavedChangesDialogOpen(true);
    } else {
      setSelectedWorkflowId(workflow.id);
      onWorkflowSelect(workflow);
    }
  };

  const handleDiscardAndSwitch = () => {
    if (workflowToSelect) {
      setSelectedWorkflowId(workflowToSelect.id);
      onWorkflowSelect(workflowToSelect);
    }
    setIsUnsavedChangesDialogOpen(false);
    setWorkflowToSelect(null);
  };

  const handleSaveAndSwitch = async () => {
    if (workflowToSelect) {
      setIsSwitching(true);
      await onSaveWorkflow();
      onWorkflowSelect(workflowToSelect);
      setSelectedWorkflowId(workflowToSelect.id);
      setIsSwitching(false);
    }
    setIsUnsavedChangesDialogOpen(false);
    setWorkflowToSelect(null);
  };

  const handleEditClick = (workflow: Workflow) => {
    handleWorkflowSelect(workflow);
    setWorkflowName(workflow.name);
    setWorkflowVersion(workflow.version);
    setWorkflowDescription(workflow.description || "");
    setVersionError(null);
    setEditDialogOpen(true);
  };

  const handleActivateClick = async (workflow: Workflow) => {
    setWorkflowToActivate(workflow);
    setIsActivateDialogOpen(true);
  };

  const handleActiveWorkflowChange = async () => {
    setIsActivating(true);

    onActiveWorkflowChange(workflowToActivate);
    setSelectedWorkflowId(workflowToActivate.id);
    onWorkflowSelect(workflowToActivate);

    setWorkflowToActivate(null);
    setIsActivateDialogOpen(false);
    setIsActivating(false);
  };

  const closeDialogs = () => {
    setCreateDialogOpen(false);
    setEditDialogOpen(false);
    setVersionError(null);
    // setWorkflowName("");
    // setWorkflowDescription("");
  };

  const handleUpdateWorkflow = async () => {
    if (!workflowName.trim() && !currentWorkflow.id) {
      return;
    }

    const finalVersion = workflowVersion != "" ? workflowVersion : currentWorkflow.version;
    
    // Check for duplicate version (excluding current workflow)
    if (isVersionDuplicate(workflows, finalVersion, currentWorkflow.id)) {
      setVersionError(`Version "${finalVersion}" already exists. Please choose a different version number.`);
      return;
    }

    setError(null);
    setVersionError(null);
    try {
      const workflowToSave = {
        ...currentWorkflow,
        name: workflowName != "" ? workflowName : currentWorkflow.name,
        description:
          workflowDescription != ""
            ? workflowDescription
            : currentWorkflow.description,
        version: finalVersion,
      };

      await updateWorkflow(currentWorkflow.id, workflowToSave);
      closeDialogs();
      loadWorkflows();
    } catch (err) {
      setError("Failed to save workflow. Please try again.");
    }
  };

  const handleDeleteClick = async (workflow: Workflow) => {
    setWorkflowToDelete(workflow);
    setIsDeleteDialogOpen(true);
  };

  // Handle delete workflow
  const handleDeleteWorkflow = async () => {
    try {
      setIsDeleting(true);
      const workflowId = workflowToDelete.id;
      const isCurrentlySelected = workflowId === selectedWorkflowId;
      
      // Find the previous version to switch to if we're deleting the current workflow
      let previousVersion: Workflow | null = null;
      if (isCurrentlySelected) {
        previousVersion = findPreviousVersion(workflows, workflowToDelete);
      }
      
      await deleteWorkflow(workflowId);
      const updatedWorkflows = workflows.filter((w) => w.id !== workflowId);
      setWorkflows(updatedWorkflows);
      
      // Auto-switch to previous version if we deleted the current workflow
      if (isCurrentlySelected && previousVersion) {
        setSelectedWorkflowId(previousVersion.id);
        onWorkflowSelect(previousVersion);
      } else if (isCurrentlySelected && updatedWorkflows.length === 0) {
        // If no workflows left, clear selection
        setSelectedWorkflowId(null);
      }
    } catch (err) {
      setError("Failed to delete workflow. Please try again.");
    } finally {
      setWorkflowToDelete(null);
      setIsDeleteDialogOpen(false);
      setIsDeleting(false);
    }
  };

  // // Format date
  // const formatDate = (dateString: string) => {
  //   return new Date(dateString).toLocaleString();
  // };

  if (!isOpen) return null;

  return (
    <div
      className="fixed top-2 right-2 h-[calc(100vh-1rem)] w-80 bg-white border shadow-lg rounded-lg transform transition-transform duration-200 ease-in-out translate-x-0 animate-in slide-in-from-right"
    >
      <div className="h-full flex flex-col">
        <div className="p-4 border-b">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold">Saved Versions</h2>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-4">
          <div className="flex items-center space-x-2 mb-4">
            <Button
              onClick={() => {
                setWorkflowName(currentWorkflow.name || "");
                setWorkflowVersion(calculateNextVersion(workflows));
                setWorkflowDescription(currentWorkflow.description || "");
                setVersionError(null);
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
                onClick={() => handleWorkflowSelect(workflow)}
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <div className="font-medium truncate">{workflow.name}</div>
                    {workflow.id === activeWorkflowId && (
                      <span className="inline-flex items-center gap-1 text-xs text-green-600 bg-green-50 px-2 py-0.5 rounded-full">
                        <Power className="h-3 w-3" />
                        Active
                      </span>
                    )}
                  </div>
                  <div className="text-xs text-gray-500 truncate">
                    {workflow.description || "No description"}
                  </div>
                  <span className="inline-flex items-center gap-1 text-xs text-white bg-gray-400 px-2 py-0.5 rounded-full">
                    v{workflow.version}
                  </span>
                </div>
                <div className="flex items-center space-x-1">
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="ghost" size="icon">
                        <MoreVertical className="h-4 w-4" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem
                        onClick={(e) => {
                          e.stopPropagation();
                          handleEditClick(workflow);
                        }}
                      >
                        <Edit className="mr-2 h-4 w-4" />
                        <span>Edit</span>
                      </DropdownMenuItem>
                      <DropdownMenuItem
                        onClick={(e) => {
                          e.stopPropagation();
                          handleActivateClick(workflow);
                        }}
                        disabled={workflow.id === activeWorkflowId}
                      >
                        <Power className="mr-2 h-4 w-4" />
                        <span>Activate</span>
                      </DropdownMenuItem>
                      <DropdownMenuSeparator />
                      <DropdownMenuItem
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDeleteClick(workflow);
                        }}
                        className="text-destructive focus:text-destructive"
                        disabled={workflow.id === activeWorkflowId}
                      >
                        <Trash2 className="mr-2 h-4 w-4" />
                        <span>Delete</span>
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
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
            <div className="space-y-2">
              <Label htmlFor="version">Version</Label>
              <Input
                id="version"
                placeholder="Version number"
                value={workflowVersion}
                onChange={(e) => {
                  setWorkflowVersion(e.target.value);
                  setVersionError(null); // Clear version error when user types
                }}
                disabled={editDialogOpen}
                className={versionError ? "border-red-500" : ""}
              />
              {versionError && (
                <p className="text-sm text-red-600">{versionError}</p>
              )}
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
              disabled={!workflowName.trim() || !workflowVersion.trim()}
              className="flex items-center gap-2"
            >
              <Save className="h-4 w-4" />
              Save
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Workflow Dialog */}
      <ConfirmDialog
        isOpen={isDeleteDialogOpen}
        onOpenChange={setIsDeleteDialogOpen}
        onConfirm={handleDeleteWorkflow}
        isInProgress={isDeleting}
        itemName={workflowToDelete?.name || ""}
        description={`This action cannot be undone. This will permanently delete workflow "${workflowToDelete?.name}".`}
      />

      {/* Activate Workflow Dialog */}
      <ConfirmDialog
        isOpen={isActivateDialogOpen}
        onOpenChange={setIsActivateDialogOpen}
        onConfirm={handleActiveWorkflowChange}
        isInProgress={isActivating}
        primaryButtonText="Activate"
        itemName={workflowToActivate?.name || ""}
        description={`This action will make workflow "${workflowToActivate?.name}" the active workflow of this agent.`}
      />

      {/* Save or Discard Changes Dialog */}
      <ConfirmDialog
        isOpen={isUnsavedChangesDialogOpen}
        onOpenChange={setIsUnsavedChangesDialogOpen}
        onConfirm={handleSaveAndSwitch}
        isInProgress={isSwitching}
        primaryButtonText="Save"
        secondaryButtonText="Discard"
        onCancel={handleDiscardAndSwitch}
        title="You have unsaved changes!"
        description="Would you like to save or discard them?"
      />
    </div>
  );
};

export default WorkflowsSavedPanel;
