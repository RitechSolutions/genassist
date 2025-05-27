import React, { useState, useEffect, useCallback } from 'react';
import { 
  Dialog, 
  DialogContent, 
  DialogHeader, 
  DialogTitle,
  DialogFooter,
  DialogDescription
} from '@/components/ui/dialog';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow
} from '@/components/ui/table';
import { Button } from '@/components/button';
import { Input } from '@/components/input';
import { Label } from '@/components/label';
import { Workflow, GraphData } from '@/interfaces/workflow.interface';
import { 
  getAllWorkflows, 
  getWorkflowById, 
  deleteWorkflow 
} from '@/services/workflows';
import { Loader2, Trash2, Download, Save, PlayCircle } from 'lucide-react';
import { Node, Edge } from 'reactflow';
import { 
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import WorkflowTestDialog from './WorkflowTestDialog';

interface WorkflowManagerProps {
  workflow: Workflow;
  isOpen: boolean;
  onClose: () => void;
  onLoad: (workflow: Workflow) => void;
  onSave: (workflow: Workflow) => Promise<void>;
}

const WorkflowManager: React.FC<WorkflowManagerProps> = ({
  workflow,
  isOpen,
  onClose,
  onLoad,
  onSave,
}) => {
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [loading, setLoading] = useState(false);
  const [saveDialogOpen, setSaveDialogOpen] = useState(false);
  const [workflowName, setWorkflowName] = useState('');
  const [workflowDescription, setWorkflowDescription] = useState('');
  const [saving, setSaving] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [workflowToDelete, setWorkflowToDelete] = useState<Workflow | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [testDialogOpen, setTestDialogOpen] = useState(false);
  const [workflowToTest, setWorkflowToTest] = useState<{
    name: string;
    configuration: GraphData | null;
  }>({ name: '', configuration: null });

  // Load workflows
  const loadWorkflows = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const workflowList = await getAllWorkflows();
      setWorkflows(workflowList || []);
    } catch (err) {
      console.error('Error loading workflows:', err);
      setError('Failed to load workflows. Please try again.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (isOpen) {
      loadWorkflows();
    }
  }, [isOpen, loadWorkflows]);

  // Load a specific workflow
  const handleLoadWorkflow = async (workflow: Workflow) => {
    setLoading(true);
    setError(null);
    try {
      const workflowData = await getWorkflowById(workflow.id);
      if (workflowData && workflowData.configuration) {
        onLoad(workflowData);
        onClose();
      }
    } catch (err) {
      console.error('Error loading workflow:', err);
      setError('Failed to load workflow. The format may be invalid.');
    } finally {
      setLoading(false);
    }
  };

  // Handle test workflow
  const handleTestWorkflow = async (workflow: Workflow) => {
    setLoading(true);
    setError(null);
    try {
      setWorkflowToTest(workflow);
      setTestDialogOpen(true);
    } catch (err) {
      console.error('Error loading workflow for testing:', err);
      setError('Failed to load workflow for testing. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  // Handle save workflow
  const handleSaveWorkflow = async () => {
    if (!workflowName.trim()) {
      return;
    }
    
    setSaving(true);
    setError(null);
    try {
      if (workflow.id) {
        await onSave({
          id: workflow.id,
          name: workflowName,
          description: workflowDescription,
          configuration: workflow.configuration
        });
      } else {
        await onSave({
          name: workflowName,
          description: workflowDescription,
          configuration: workflow.configuration
        });
      }
      setSaveDialogOpen(false);
      setWorkflowName('');
      setWorkflowDescription('');
      loadWorkflows();
    } catch (err) {
      console.error('Error saving workflow:', err);
      setError('Failed to save workflow. Please try again.');
    } finally {
      setSaving(false);
    }
  };

  // Handle delete workflow
  const handleDeleteWorkflow = async () => {
    if (!workflowToDelete) return;
    
    setLoading(true);
    setError(null);
    try {
      await deleteWorkflow(workflowToDelete.id);
      setWorkflows(workflows.filter(w => w.id !== workflowToDelete.id));
      setDeleteDialogOpen(false);
      setWorkflowToDelete(null);
    } catch (err) {
      console.error('Error deleting workflow:', err);
      setError('Failed to delete workflow. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  // Open save dialog
  const openSaveDialog = () => {
    if (workflow.configuration.nodes.length === 0) {
      setError('Cannot save an empty workflow. Add some nodes first.');
      return;
    }
    setSaveDialogOpen(true);
    setError(null);
  };

  // Format date
  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString();
  };

  return (
    <>
      <Dialog open={isOpen} onOpenChange={onClose}>
        <DialogContent className="sm:max-w-3xl">
          <DialogHeader>
            <DialogTitle>Workflow Manager</DialogTitle>
            <DialogDescription>
              Manage your saved graph workflows
            </DialogDescription>
          </DialogHeader>

          <div className="my-4">
            <Button 
              onClick={openSaveDialog} 
              className="mb-4 flex items-center gap-2"
              disabled={workflow.configuration.nodes.length === 0}
            >
              <Save className="h-4 w-4" />
              Save Current Graph
            </Button>

            {error && (
              <div className="bg-red-50 border border-red-200 text-red-600 p-3 rounded-md mb-4">
                {error}
              </div>
            )}

            {loading ? (
              <div className="flex justify-center p-8">
                <Loader2 className="h-8 w-8 animate-spin text-gray-500" />
              </div>
            ) : workflows.length === 0 ? (
              <div className="text-center py-8 text-gray-500">
                No saved workflows found. Create your first one!
              </div>
            ) : (
              <div className="border rounded-md">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Name</TableHead>
                      <TableHead>Description</TableHead>
                      <TableHead>Created</TableHead>
                      <TableHead>Updated</TableHead>
                      <TableHead className="w-36">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {workflows.map((workflow) => (
                      <TableRow key={workflow.id}>
                        <TableCell className="font-medium">{workflow.name}</TableCell>
                        <TableCell className="max-w-48 truncate">
                          {workflow.description || "-"}
                        </TableCell>
                        <TableCell>{formatDate(workflow.created_at)}</TableCell>
                        <TableCell>{formatDate(workflow.updated_at)}</TableCell>
                        <TableCell>
                          <div className="flex items-center space-x-2">
                            <Button
                              variant="ghost"
                              size="icon"
                              title="Load Workflow"
                              onClick={() => handleLoadWorkflow(workflow)}
                            >
                              <Download className="h-4 w-4" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="icon"
                              title="Test Workflow"
                              onClick={() => handleTestWorkflow(workflow)}
                              className="text-green-500 hover:text-green-700"
                            >
                              <PlayCircle className="h-4 w-4" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="icon"
                              title="Delete Workflow"
                              onClick={() => {
                                setWorkflowToDelete(workflow);
                                setDeleteDialogOpen(true);
                              }}
                              className="text-red-500 hover:text-red-700"
                            >
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}
          </div>

          <DialogFooter>
            <Button variant="secondary" onClick={onClose}>
              Close
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Save Workflow Dialog */}
      <Dialog open={saveDialogOpen} onOpenChange={setSaveDialogOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Save Workflow</DialogTitle>
            <DialogDescription>
              Enter a name and optional description for your workflow
            </DialogDescription>
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
            <Button variant="outline" onClick={() => setSaveDialogOpen(false)}>
              Cancel
            </Button>
            <Button 
              onClick={handleSaveWorkflow} 
              disabled={saving || !workflowName.trim()}
              className="flex items-center gap-2"
            >
              {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
              Save
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Are you sure?</AlertDialogTitle>
            <AlertDialogDescription>
              This will permanently delete the workflow "{workflowToDelete?.name}".
              This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel onClick={() => setWorkflowToDelete(null)}>
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction 
              onClick={handleDeleteWorkflow}
              className="bg-red-500 hover:bg-red-600 text-white"
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Test Workflow Dialog */}
      <WorkflowTestDialog
        isOpen={testDialogOpen}
        onClose={() => setTestDialogOpen(false)}
        workflowName={workflowToTest.name}
        configuration={workflowToTest.configuration}
      />
    </>
  );
};

export default WorkflowManager; 