import React, { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { toast } from "react-hot-toast";
import { SidebarProvider, SidebarTrigger } from "@/components/sidebar";
import { AppSidebar } from "@/layout/app-sidebar";
import { useIsMobile } from "@/hooks/useMobile";
import { Button } from "@/components/button";
import { Input } from "@/components/input";
import { Textarea } from "@/components/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/select";
import {
  ChevronLeft,
  Play,
  Clock,
  CheckCircle2,
  XCircle,
  AlertCircle,
  Download,
  Star,
  StarOff,
  Trash2,
  Plus,
  ExternalLink,
  FileCode,
  Calendar,
} from "lucide-react";
import { Badge } from "@/components/badge";
import { getMLModel } from "@/services/mlModels";
import { MLModel } from "@/interfaces/ml-model.interface";
import {
  getModelPipelineConfigs,
  createPipelineConfig,
  updatePipelineConfig,
  deletePipelineConfig,
  getModelPipelineRuns,
  createPipelineRun,
  promotePipelineRun,
  getPipelineRunArtifacts,
} from "@/services/mlModelPipelines";
import {
  TrainingPipelineConfig,
  PipelineRun,
  PipelineArtifact,
} from "@/interfaces/ml-model-pipeline.interface";
import { getAllWorkflows, createWorkflow } from "@/services/workflows";
import { Workflow, WorkflowCreatePayload } from "@/interfaces/workflow.interface";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Label } from "@/components/label";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import JsonViewer from "@/components/JsonViewer";
import { v4 as uuidv4 } from "uuid";

const MLModelDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const isMobile = useIsMobile();
  const [model, setModel] = useState<MLModel | null>(null);
  const [loading, setLoading] = useState(true);
  const [pipelineConfigs, setPipelineConfigs] = useState<TrainingPipelineConfig[]>([]);
  const [pipelineRuns, setPipelineRuns] = useState<PipelineRun[]>([]);
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [selectedRun, setSelectedRun] = useState<PipelineRun | null>(null);
  const [runArtifacts, setRunArtifacts] = useState<PipelineArtifact[]>([]);
  const [showRunDetails, setShowRunDetails] = useState(false);
  const [showConfigDialog, setShowConfigDialog] = useState(false);
  const [showCreateWorkflowDialog, setShowCreateWorkflowDialog] = useState(false);
  const [selectedWorkflowId, setSelectedWorkflowId] = useState<string>("");
  const [cronSchedule, setCronSchedule] = useState<string>("");
  const [newWorkflowName, setNewWorkflowName] = useState("");
  const [newWorkflowDescription, setNewWorkflowDescription] = useState("");
  const [isCreatingRun, setIsCreatingRun] = useState(false);
  const [configToDelete, setConfigToDelete] = useState<TrainingPipelineConfig | null>(null);
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  useEffect(() => {
    if (id) {
      fetchModel();
      fetchPipelineConfigs();
      fetchPipelineRuns();
      fetchWorkflows();
    }
  }, [id]);

  const fetchModel = async () => {
    if (!id) return;
    try {
      setLoading(true);
      const data = await getMLModel(id);
      setModel(data);
    } catch (error) {
      toast.error("Failed to load ML model");
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const fetchPipelineConfigs = async () => {
    if (!id) return;
    try {
      const configs = await getModelPipelineConfigs(id);
      setPipelineConfigs(configs);
    } catch (error) {
      console.error("Error fetching pipeline configs:", error);
    }
  };

  const fetchPipelineRuns = async () => {
    if (!id) return;
    try {
      const runs = await getModelPipelineRuns(id);
      setPipelineRuns(runs.sort((a, b) => {
        const dateA = new Date(a.created_at || 0).getTime();
        const dateB = new Date(b.created_at || 0).getTime();
        return dateB - dateA;
      }));
    } catch (error) {
      console.error("Error fetching pipeline runs:", error);
    }
  };

  const fetchWorkflows = async () => {
    try {
      const allWorkflows = await getAllWorkflows();
      // Show all workflows - user can select any workflow for training pipeline
      // Filtering by training nodes is optional but we show all for flexibility
      setWorkflows(allWorkflows);
    } catch (error) {
      console.error("Error fetching workflows:", error);
    }
  };

  const isValidCron = (cron: string): boolean => {
    if (!cron.trim()) return true; // Empty is valid (no schedule)
    const cronRegex = /^(((\*|\d+)(-\d+)?)(\/\d+)?)(,((\*|\d+)(-\d+)?)(\/\d+)?)*\s+(((\*|\d+)(-\d+)?)(\/\d+)?)(,((\*|\d+)(-\d+)?)(\/\d+)?)*\s+(((\*|\d+)(-\d+)?)(\/\d+)?)(,((\*|\d+)(-\d+)?)(\/\d+)?)*\s+(((\*|\d+)(-\d+)?)(\/\d+)?)(,((\*|\d+)(-\d+)?)(\/\d+)?)*\s+(((\*|\d+)(-\d+)?)(\/\d+)?)(,((\*|\d+)(-\d+)?)(\/\d+)?)*$/;
    return cronRegex.test(cron.trim());
  };

  const handleCreateConfig = async () => {
    if (!id || !selectedWorkflowId) {
      toast.error("Please select a workflow");
      return;
    }

    if (cronSchedule && !isValidCron(cronSchedule)) {
      toast.error("Invalid cron expression. Expected format: * * * * *");
      return;
    }

    try {
      await createPipelineConfig(id, {
        model_id: id,
        workflow_id: selectedWorkflowId,
        cron_schedule: cronSchedule || null,
        is_default: pipelineConfigs.length === 0,
      });
      toast.success("Pipeline configuration created successfully");
      setShowConfigDialog(false);
      setSelectedWorkflowId("");
      setCronSchedule("");
      fetchPipelineConfigs();
    } catch (error) {
      toast.error("Failed to create pipeline configuration");
      console.error(error);
    }
  };

  const handleCreateWorkflow = async () => {
    if (!newWorkflowName.trim()) {
      toast.error("Please enter a workflow name");
      return;
    }

    try {
      // Create a basic training workflow
      // Note: agent_id is required but for ML model training workflows,
      // we use an empty string as a placeholder. The workflow should be
      // properly configured in the Workflow Studio.
      const newWorkflow: WorkflowCreatePayload = {
        name: newWorkflowName,
        description: newWorkflowDescription,

        version: "1.0.0",
      };

      const created = await createWorkflow(newWorkflow);
      toast.success("Workflow created successfully. You can configure it in the Workflow Studio.");
      setShowCreateWorkflowDialog(false);
      setNewWorkflowName("");
      setNewWorkflowDescription("");
      await fetchWorkflows();
      setSelectedWorkflowId(created.id || "");
      setShowConfigDialog(true);
    } catch (error) {
      toast.error("Failed to create workflow");
      console.error(error);
    }
  };

  const handleRunPipeline = async (configId: string) => {
    if (!id) return;
    try {
      setIsCreatingRun(true);
      await createPipelineRun(id, {
        model_id: id,
        pipeline_config_id: configId,
        workflow_id: pipelineConfigs.find(c => c.id === configId)?.workflow_id || "",
      });
      toast.success("Pipeline run started");
      fetchPipelineRuns();
    } catch (error) {
      toast.error("Failed to start pipeline run");
      console.error(error);
    } finally {
      setIsCreatingRun(false);
    }
  };

  const handlePromoteRun = async (runId: string) => {
    if (!id) return;
    try {
      await promotePipelineRun(id, runId);
      toast.success("Pipeline run promoted as default configuration");
      fetchPipelineConfigs();
      fetchPipelineRuns();
    } catch (error) {
      toast.error("Failed to promote pipeline run");
      console.error(error);
    }
  };

  const handleViewRunDetails = async (run: PipelineRun) => {
    setSelectedRun(run);
    if (id && run.id) {
      try {
        const artifacts = await getPipelineRunArtifacts(id, run.id);
        setRunArtifacts(artifacts);
      } catch (error) {
        console.error("Error fetching artifacts:", error);
      }
    }
    setShowRunDetails(true);
  };

  const handleSetDefault = async (configId: string) => {
    if (!id) return;
    try {
      // Set all configs to not default, then set this one as default
      const config = pipelineConfigs.find(c => c.id === configId);
      if (config) {
        await updatePipelineConfig(id, configId, {
          is_default: true,
        });
        // Update other configs to not be default
        for (const otherConfig of pipelineConfigs) {
          if (otherConfig.id !== configId && otherConfig.is_default) {
            await updatePipelineConfig(id, otherConfig.id, {
              is_default: false,
            });
          }
        }
        toast.success("Default configuration updated");
        fetchPipelineConfigs();
      }
    } catch (error) {
      toast.error("Failed to update default configuration");
      console.error(error);
    }
  };

  const handleDeleteConfig = async () => {
    if (!id || !configToDelete) return;
    try {
      setIsDeleting(true);
      await deletePipelineConfig(id, configToDelete.id);
      toast.success("Pipeline configuration deleted");
      fetchPipelineConfigs();
    } catch (error) {
      toast.error("Failed to delete pipeline configuration");
      console.error(error);
    } finally {
      setIsDeleting(false);
      setIsDeleteDialogOpen(false);
      setConfigToDelete(null);
    }
  };

  const getStatusBadge = (status: string) => {
    const statusConfig: Record<string, { label: string; variant: "default" | "secondary" | "destructive" | "outline" }> = {
      completed: { label: "Completed", variant: "default" },
      running: { label: "Running", variant: "secondary" },
      failed: { label: "Failed", variant: "destructive" },
      pending: { label: "Pending", variant: "outline" },
      cancelled: { label: "Cancelled", variant: "outline" },
    };
    const config = statusConfig[status] || { label: status, variant: "outline" as const };
    return <Badge variant={config.variant}>{config.label}</Badge>;
  };

  const getModelTypeLabel = (type: string) => {
    const labels: Record<string, string> = {
      xgboost: "XGBoost",
      random_forest: "Random Forest",
      linear_regression: "Linear Regression",
      logistic_regression: "Logistic Regression",
      other: "Other",
    };
    return labels[type] || type;
  };

  if (loading) {
    return (
      <SidebarProvider>
        <div className="min-h-screen flex w-full">
          {!isMobile && <AppSidebar />}
          <main className="flex-1 flex flex-col bg-zinc-100 relative">
            <SidebarTrigger className="fixed top-4 z-10 h-8 w-8 bg-white/50 backdrop-blur-sm hover:bg-white/70 rounded-full shadow-md transition-[left] duration-200" />
            <div className="flex-1 p-8">
              <div className="max-w-7xl mx-auto">
                <div className="flex justify-center items-center py-12">
                  <div className="text-sm text-gray-500">Loading model details...</div>
                </div>
              </div>
            </div>
          </main>
        </div>
      </SidebarProvider>
    );
  }

  if (!model) {
    return (
      <SidebarProvider>
        <div className="min-h-screen flex w-full">
          {!isMobile && <AppSidebar />}
          <main className="flex-1 flex flex-col bg-zinc-100 relative">
            <SidebarTrigger className="fixed top-4 z-10 h-8 w-8 bg-white/50 backdrop-blur-sm hover:bg-white/70 rounded-full shadow-md transition-[left] duration-200" />
            <div className="flex-1 p-8">
              <div className="max-w-7xl mx-auto">
                <div className="flex flex-col items-center justify-center py-12 gap-4">
                  <AlertCircle className="h-12 w-12 text-gray-400" />
                  <h3 className="font-medium text-lg">Model not found</h3>
                  <Button onClick={() => navigate("/ml-models")}>Back to ML Models</Button>
                </div>
              </div>
            </div>
          </main>
        </div>
      </SidebarProvider>
    );
  }


  return (
    <SidebarProvider>
      <div className="min-h-screen flex w-full">
        {!isMobile && <AppSidebar />}
        <main className="flex-1 flex flex-col bg-zinc-100">
          <div className="flex-1 p-8">
            <div className="max-w-7xl mx-auto">
              <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Button
          variant="ghost"
          size="icon"
          onClick={() => navigate("/ml-models")}
        >
          <ChevronLeft className="h-5 w-5" />
        </Button>
        <div>
          <h2 className="text-3xl font-bold">{model.name}</h2>
          <p className="text-zinc-400 font-normal">{model.description}</p>
        </div>
      </div>

      {/* Section 1: Model Details */}
      <div className="rounded-lg border bg-white p-6 mb-6">
        <h3 className="text-xl font-semibold mb-6">Model Information</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          <div>
            <Label className="text-sm text-gray-500 mb-1 block">Model Type</Label>
            <p className="text-sm font-medium">{getModelTypeLabel(model.model_type)}</p>
          </div>
          <div>
            <Label className="text-sm text-gray-500 mb-1 block">Target Variable</Label>
            <p className="text-sm font-medium">{model.target_variable}</p>
          </div>
          <div>
            <Label className="text-sm text-gray-500 mb-1 block">Features</Label>
            <p className="text-sm font-medium">{model.features.length} features</p>
            <p className="text-xs text-gray-500 mt-1">{model.features.join(", ")}</p>
          </div>
          {model.created_at && (
            <div>
              <Label className="text-sm text-gray-500 mb-1 block">Created At</Label>
              <p className="text-sm font-medium">
                {new Date(model.created_at).toLocaleString()}
              </p>
            </div>
          )}
          {model.updated_at && (
            <div>
              <Label className="text-sm text-gray-500 mb-1 block">Updated At</Label>
              <p className="text-sm font-medium">
                {new Date(model.updated_at).toLocaleString()}
              </p>
            </div>
          )}
        </div>

        {model.pkl_file && (
          <div className="mt-6">
            <Label className="text-sm text-gray-500 mb-1 block">Model File</Label>
            <div className="flex items-center gap-2 mt-1">
              <FileCode className="h-4 w-4" />
              <p className="text-sm font-medium">{model.pkl_file}</p>
            </div>
          </div>
        )}

        {model.inference_params && Object.keys(model.inference_params).length > 0 && (
          <div className="mt-6 pt-6 border-t">
            <Label className="text-sm text-gray-500 mb-2 block">Inference Parameters</Label>
            <div className="bg-gray-50 rounded-md p-4">
              <JsonViewer data={model.inference_params} />
            </div>
          </div>
        )}
      </div>

      {/* Section 2: Training Pipeline & Runs */}
      <div className="space-y-6">
        {/* Assigned Workflow Section */}
        <div className="rounded-lg border bg-white p-6">
          <div className="flex items-center justify-between mb-6">
            <h3 className="text-xl font-semibold">Training Pipeline Configuration</h3>
            <Button onClick={() => setShowConfigDialog(true)}>
              <Plus className="h-4 w-4 mr-2" />
              {pipelineConfigs.length === 0 ? "Configure Pipeline" : "Add Configuration"}
            </Button>
          </div>

          {pipelineConfigs.length === 0 ? (
            <div className="text-center py-12">
              <AlertCircle className="h-12 w-12 text-gray-400 mx-auto mb-4" />
              <h4 className="font-medium text-lg mb-2">No pipeline configuration</h4>
              <p className="text-sm text-gray-500 mb-4">
                Configure a training workflow to start training this model.
              </p>
              <Button onClick={() => setShowConfigDialog(true)}>
                <Plus className="h-4 w-4 mr-2" />
                Configure Pipeline
              </Button>
            </div>
          ) : (
            <div className="space-y-4">
              {pipelineConfigs.map((config) => {
                const workflow = workflows.find(w => w.id === config.workflow_id);
                return (
                  <div key={config.id} className="border rounded-lg p-4 bg-gray-50">
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-2">
                          <h4 className="text-lg font-semibold">
                            {workflow?.name || "Unknown Workflow"}
                          </h4>
                          {config.is_default && (
                            <Badge variant="default" className="gap-1">
                              <Star className="h-3 w-3" />
                              Default
                            </Badge>
                          )}
                          {config.cron_schedule && (
                            <Badge variant="outline" className="gap-1">
                              <Calendar className="h-3 w-3" />
                              Scheduled
                            </Badge>
                          )}
                        </div>
                        {workflow?.description && (
                          <p className="text-sm text-gray-600 mb-2">{workflow.description}</p>
                        )}
                        <div className="flex flex-wrap gap-4 text-xs text-gray-500">
                          {workflow?.version && (
                            <span>Version: {workflow.version}</span>
                          )}
                          {config.cron_schedule && (
                            <span className="flex items-center gap-1">
                              <Clock className="h-3 w-3" />
                              {config.cron_schedule}
                            </span>
                          )}
                        </div>
                      </div>
                      <div className="flex gap-2 ml-4">
                        {!config.is_default && (
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => handleSetDefault(config.id)}
                          >
                            <StarOff className="h-4 w-4 mr-1" />
                            Set Default
                          </Button>
                        )}
                        <Button
                          variant="default"
                          size="sm"
                          onClick={() => handleRunPipeline(config.id)}
                          disabled={isCreatingRun}
                        >
                          <Play className="h-4 w-4 mr-1" />
                          Run Now
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => {
                            setConfigToDelete(config);
                            setIsDeleteDialogOpen(true);
                          }}
                          className="text-red-500 hover:text-red-700"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Pipeline Runs Section */}
        <div className="rounded-lg border bg-white p-6">
          <div className="flex items-center justify-between mb-6">
            <h3 className="text-xl font-semibold">Pipeline Execution History</h3>
            {pipelineRuns.length > 0 && (
              <Badge variant="outline">{pipelineRuns.length} runs</Badge>
            )}
          </div>

          {pipelineRuns.length === 0 ? (
            <div className="text-center py-12">
              <Clock className="h-12 w-12 text-gray-400 mx-auto mb-4" />
              <h4 className="font-medium text-lg mb-2">No pipeline runs</h4>
              <p className="text-sm text-gray-500">
                Pipeline execution history will appear here after you run a training pipeline.
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              {pipelineRuns.map((run) => {
                const workflow = workflows.find(w => w.id === run.workflow_id);
                const config = pipelineConfigs.find(c => c.id === run.pipeline_config_id);
                const isSuccessful = run.status === "completed";
                const duration = run.started_at && run.completed_at
                  ? Math.round((new Date(run.completed_at).getTime() - new Date(run.started_at).getTime()) / 1000 / 60)
                  : null;
                
                return (
                  <div key={run.id} className="border rounded-lg p-4 hover:bg-gray-50 transition-colors">
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-2">
                          <h4 className="text-base font-semibold">
                            {workflow?.name || "Unknown Workflow"}
                          </h4>
                          {getStatusBadge(run.status)}
                          {config?.is_default && (
                            <Badge variant="outline" className="text-xs">Default Config</Badge>
                          )}
                        </div>
                        <div className="flex flex-wrap gap-4 text-sm text-gray-600">
                          {run.started_at && (
                            <span className="flex items-center gap-1">
                              <Clock className="h-3 w-3" />
                              {new Date(run.started_at).toLocaleString()}
                            </span>
                          )}
                          {duration !== null && (
                            <span>Duration: {duration} min</span>
                          )}
                        </div>
                        {run.error_message && (
                          <div className="mt-2 p-2 bg-red-50 border border-red-200 rounded text-sm text-red-700">
                            <AlertCircle className="h-4 w-4 inline mr-1" />
                            {run.error_message}
                          </div>
                        )}
                        {isSuccessful && run.execution_output && (
                          <div className="mt-2 text-xs text-gray-500">
                            Execution completed successfully
                          </div>
                        )}
                      </div>
                      <div className="flex gap-2 ml-4">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleViewRunDetails(run)}
                        >
                          <ExternalLink className="h-4 w-4 mr-1" />
                          Details
                        </Button>
                        {isSuccessful && (
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => handlePromoteRun(run.id)}
                            className="border-green-200 text-green-700 hover:bg-green-50"
                          >
                            <Star className="h-4 w-4 mr-1" />
                            Promote
                          </Button>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* Create Configuration Dialog */}
      <Dialog open={showConfigDialog} onOpenChange={setShowConfigDialog}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Configure Training Pipeline</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div>
              <Label>Select Workflow</Label>
              <Select value={selectedWorkflowId} onValueChange={setSelectedWorkflowId}>
                <SelectTrigger>
                  <SelectValue placeholder="Select a workflow" />
                </SelectTrigger>
                <SelectContent>
                  {workflows.map((workflow) => (
                    <SelectItem key={workflow.id} value={workflow.id || ""}>
                      {workflow.name} {workflow.version && `(v${workflow.version})`}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <div className="mt-2 flex gap-2">
                <Button
                  variant="link"
                  size="sm"
                  onClick={() => {
                    setShowConfigDialog(false);
                    setShowCreateWorkflowDialog(true);
                  }}
                >
                  <Plus className="h-4 w-4 mr-1" />
                  Create New Workflow
                </Button>
                <Button
                  variant="link"
                  size="sm"
                  onClick={() => {
                    window.open("/ai-agents", "_blank");
                  }}
                >
                  <ExternalLink className="h-4 w-4 mr-1" />
                  Open Workflow Studio
                </Button>
              </div>
            </div>
            <div>
              <Label>Cron Schedule (Optional)</Label>
              <Input
                placeholder="* * * * * (e.g., 0 0 * * * for daily at midnight)"
                value={cronSchedule}
                onChange={(e) => setCronSchedule(e.target.value)}
              />
              <p className="text-xs text-gray-500 mt-1">
                Leave empty to run manually only. Format: minute hour day month weekday
              </p>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowConfigDialog(false)}>
              Cancel
            </Button>
            <Button onClick={handleCreateConfig}>Create Configuration</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Create Workflow Dialog */}
      <Dialog open={showCreateWorkflowDialog} onOpenChange={setShowCreateWorkflowDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create New Workflow</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div>
              <Label>Workflow Name</Label>
              <Input
                value={newWorkflowName}
                onChange={(e) => setNewWorkflowName(e.target.value)}
                placeholder="Enter workflow name"
              />
            </div>
            <div>
              <Label>Description (Optional)</Label>
              <Textarea
                value={newWorkflowDescription}
                onChange={(e) => setNewWorkflowDescription(e.target.value)}
                placeholder="Enter workflow description"
                rows={3}
              />
            </div>
            <p className="text-sm text-gray-500">
              After creating the workflow, you can configure it in the Workflow Studio by navigating to AI Agents → Workflow Studio.
            </p>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowCreateWorkflowDialog(false)}>
              Cancel
            </Button>
            <Button onClick={handleCreateWorkflow}>Create Workflow</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Run Details Dialog */}
      <Dialog open={showRunDetails} onOpenChange={setShowRunDetails}>
        <DialogContent className="max-w-4xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Pipeline Run Details</DialogTitle>
          </DialogHeader>
          {selectedRun && (
            <div className="space-y-6 py-4">
              <div>
                <Label className="text-sm font-semibold">Status</Label>
                <div className="mt-1">{getStatusBadge(selectedRun.status)}</div>
              </div>
              {selectedRun.started_at && (
                <div>
                  <Label className="text-sm font-semibold">Started At</Label>
                  <p className="text-sm">{new Date(selectedRun.started_at).toLocaleString()}</p>
                </div>
              )}
              {selectedRun.completed_at && (
                <div>
                  <Label className="text-sm font-semibold">Completed At</Label>
                  <p className="text-sm">{new Date(selectedRun.completed_at).toLocaleString()}</p>
                </div>
              )}
              {selectedRun.error_message && (
                <div>
                  <Label className="text-sm font-semibold text-red-600">Error</Label>
                  <p className="text-sm text-red-600">{selectedRun.error_message}</p>
                </div>
              )}
              {runArtifacts.length > 0 && (
                <div>
                  <Label className="text-sm font-semibold">Artifacts</Label>
                  <div className="mt-2 space-y-2">
                    {runArtifacts.map((artifact) => (
                      <div key={artifact.id} className="flex items-center justify-between p-3 bg-gray-50 rounded-md">
                        <div className="flex items-center gap-2">
                          <FileCode className="h-4 w-4" />
                          <div>
                            <p className="text-sm font-medium">{artifact.artifact_name}</p>
                            <p className="text-xs text-gray-500">{artifact.artifact_type}</p>
                          </div>
                        </div>
                        <Button variant="outline" size="sm">
                          <Download className="h-4 w-4 mr-1" />
                          Download
                        </Button>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              {selectedRun.execution_output && (
                <div>
                  <Label className="text-sm font-semibold">Execution Output</Label>
                  <div className="mt-2 bg-gray-50 rounded-md p-4 max-h-96 overflow-y-auto">
                    <JsonViewer data={selectedRun.execution_output} />
                  </div>
                </div>
              )}
            </div>
          )}
          <DialogFooter>
            <Button onClick={() => setShowRunDetails(false)}>Close</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <ConfirmDialog
        isOpen={isDeleteDialogOpen}
        onOpenChange={setIsDeleteDialogOpen}
        onConfirm={handleDeleteConfig}
        isInProgress={isDeleting}
        itemName={configToDelete?.workflow_id ? workflows.find(w => w.id === configToDelete.workflow_id)?.name || "configuration" : "configuration"}
        description={`This action cannot be undone. This will permanently delete the pipeline configuration.`}
      />
              </div>
            </div>
          </div>
        </main>
      </div>
    </SidebarProvider>
  );
};

export default MLModelDetail;

