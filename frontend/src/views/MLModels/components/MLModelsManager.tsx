import React, { useState, useEffect } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { toast } from "react-hot-toast";
import {
  getAllMLModels,
  createMLModel,
  updateMLModel,
  deleteMLModel,
  uploadModelFile,
  analyzePklFile,
} from "@/services/mlModels";
import { createPipelineConfig } from "@/services/mlModelPipelines";
import { getAllWorkflows, createWorkflow } from "@/services/workflows";
import { Workflow } from "@/interfaces/workflow.interface";
import { v4 as uuidv4 } from "uuid";
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
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Label } from "@/components/label";
import {
  Upload,
  X,
  Pencil,
  AlertCircle,
  CheckCircle2,
  Plus,
  ChevronLeft,
  Trash2,
  Brain,
  FileCode,
  Download,
  ExternalLink,
  Workflow as WorkflowIcon,
} from "lucide-react";
import { SearchInput } from "@/components/SearchInput";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { MLModel } from "@/interfaces/ml-model.interface";
import { Badge } from "@/components/badge";
import { downloadFile, getFileDownloadUrl } from "@/helpers/utils";
import { getApiUrlString } from "@/config/api";

const DEFAULT_FORM_DATA: MLModel = {
  id: uuidv4(),
  name: "",
  description: "",
  model_type: "xgboost",
  pkl_file: null,
  features: [],
};

const MLModelsManager: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const [items, setItems] = useState<MLModel[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [isAnalyzing, setIsAnalyzing] = useState<boolean>(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [showForm, setShowForm] = useState<boolean>(false);
  const [typeFilter, setTypeFilter] = useState<string>("all");

  const [modelToDelete, setModelToDelete] = useState<Partial<MLModel> | null>(null);
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  const [editingItem, setEditingItem] = useState<MLModel | null>(null);
  const [formData, setFormData] = useState<MLModel>(DEFAULT_FORM_DATA);
  const [featuresInput, setFeaturesInput] = useState<string>("");

  // Unified create flow: upload pkl OR configure workflow
  const [sourceType, setSourceType] = useState<"upload" | "workflow">("upload");
  const [selectedWorkflowId, setSelectedWorkflowId] = useState<string>("");
  const [cronSchedule, setCronSchedule] = useState<string>("");
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [showCreateWorkflowDialog, setShowCreateWorkflowDialog] = useState(false);
  const [newWorkflowName, setNewWorkflowName] = useState("");
  const [newWorkflowDescription, setNewWorkflowDescription] = useState("");

  // Fetch on mount and when navigating back to list (e.g. after promote on detail page)
  useEffect(() => {
    fetchItems();
  }, [location.pathname]);

  // Fetch workflows when create form is shown
  useEffect(() => {
    if (showForm && !editingItem) {
      fetchWorkflows();
    }
  }, [showForm, editingItem]);

  // When a training workflow is selected, extract features and model type from its train model node
  useEffect(() => {
    if (!editingItem && sourceType === "workflow" && selectedWorkflowId && workflows.length > 0) {
      const workflow = workflows.find((w) => w.id === selectedWorkflowId);
      const trainNode = workflow?.nodes?.find((n) => n.type === "trainModelNode");
      const nodeData = trainNode?.data as { featureColumns?: string[]; modelType?: string } | undefined;
      if (nodeData?.featureColumns?.length) {
        setFormData((prev) => ({
          ...prev,
          features: nodeData.featureColumns!,
          ...(nodeData.modelType &&
            ["xgboost", "random_forest", "linear_regression", "logistic_regression", "other", "neural_network"].includes(nodeData.modelType) && {
              model_type: (nodeData.modelType === "neural_network" ? "other" : nodeData.modelType) as MLModel["model_type"],
            }),
        }));
        setFeaturesInput(nodeData.featureColumns!.join(", "));
        if (nodeData.modelType) {
          toast.success("Features and model type loaded from workflow");
        } else {
          toast.success("Features loaded from workflow");
        }
      } else if (nodeData?.modelType && ["xgboost", "random_forest", "linear_regression", "logistic_regression", "other", "neural_network"].includes(nodeData.modelType)) {
        setFormData((prev) => ({
          ...prev,
          model_type: (nodeData.modelType === "neural_network" ? "other" : nodeData.modelType) as MLModel["model_type"],
        }));
        toast.success("Model type loaded from workflow");
      }
    }
  }, [selectedWorkflowId, workflows, sourceType, editingItem]);

  const fetchWorkflows = async () => {
    try {
      const data = await getAllWorkflows();
      setWorkflows(data ?? []);
    } catch (err) {
      console.error("Error fetching workflows:", err);
    }
  };

  const fetchItems = async () => {
    try {
      setLoading(true);
      const data = await getAllMLModels();
      setItems(data);
      setError(null);
    } catch (err) {
      setError("Failed to load ML models");
    } finally {
      setLoading(false);
    }
  };

  const handleInputChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>
  ) => {
    const { name, value } = e.target;
    setFormData((prev) => ({
      ...prev,
      [name]: value,
    }));
  };

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0] || null;
    setSelectedFile(file);

    if (file?.name.toLowerCase().endsWith(".pkl")) {
      setIsAnalyzing(true);
      try {
        const analysis = await analyzePklFile(file);
        if (analysis.error) {
          toast.error(`Could not extract metadata: ${analysis.error}`);
        } else {
          setFormData((prev) => ({
            ...prev,
            ...(analysis.model_type && {
              model_type: analysis.model_type as MLModel["model_type"],
            }),
            ...(analysis.features?.length > 0 && {
              features: analysis.features,
            }),
          }));
          if (analysis.features?.length > 0) {
            setFeaturesInput(analysis.features.join(", "));
          }
          if (analysis.model_type || analysis.features?.length) {
            toast.success("Model metadata extracted from file");
          }
        }
      } catch (err) {
        toast.error(
          `Failed to analyze file: ${err instanceof Error ? err.message : String(err)}`
        );
      } finally {
        setIsAnalyzing(false);
      }
    }
  };

  const uploadFile = async () => {
    if (!selectedFile) return null;

    setIsUploading(true);

    try {
      return await uploadModelFile(selectedFile);
    } catch (error) {
      setError(
        `Failed to upload file: ${
          error instanceof Error ? error.message : String(error)
        }`
      );
      return null;
    } finally {
      setIsUploading(false);
    }
  };

  const handleFeaturesInputChange = (value: string) => {
    setFeaturesInput(value);

    // Parse comma-separated values and update formData
    const featuresArray = value
      .split(', ')
      .map(f => f.trim())
      .filter(f => f.length > 0);

    setFormData((prev) => ({
      ...prev,
      features: featuresArray,
    }));
  };

  const isValidCron = (cron: string): boolean => {
    if (!cron.trim()) return true;
    const cronRegex = /^(((\*|\d+)(-\d+)?)(\/\d+)?)(,((\*|\d+)(-\d+)?)(\/\d+)?)*\s+(((\*|\d+)(-\d+)?)(\/\d+)?)(,((\*|\d+)(-\d+)?)(\/\d+)?)*\s+(((\*|\d+)(-\d+)?)(\/\d+)?)(,((\*|\d+)(-\d+)?)(\/\d+)?)*\s+(((\*|\d+)(-\d+)?)(\/\d+)?)(,((\*|\d+)(-\d+)?)(\/\d+)?)*\s+(((\*|\d+)(-\d+)?)(\/\d+)?)(,((\*|\d+)(-\d+)?)(\/\d+)?)*$/;
    return cronRegex.test(cron.trim());
  };

  const handleCreateWorkflow = async () => {
    if (!newWorkflowName.trim()) {
      toast.error("Please enter a workflow name");
      return;
    }
    try {
      const newWorkflow = {
        name: newWorkflowName,
        description: newWorkflowDescription,
        version: "1.0.0",
        nodes: [],
        edges: [],
        agent_id: "",
      } as Parameters<typeof createWorkflow>[0];
      const created = await createWorkflow(newWorkflow);
      toast.success("Workflow created. Configure it in the Workflow Studio.");
      setShowCreateWorkflowDialog(false);
      setNewWorkflowName("");
      setNewWorkflowDescription("");
      await fetchWorkflows();
      setSelectedWorkflowId(created.id || "");
    } catch (error) {
      toast.error("Failed to create workflow");
      console.error(error);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    const requiredFields = [
      { label: "name", isEmpty: !formData.name },
      { label: "description", isEmpty: !formData.description },
      { label: "model type", isEmpty: !formData.model_type },
    ];

    const missingFields = requiredFields
      .filter((field) => field.isEmpty)
      .map((field) => field.label)
      .map((label) => label.charAt(0).toUpperCase() + label.slice(1));

    if (missingFields.length > 0) {
      if (missingFields.length === 1) {
        toast.error(`${missingFields[0]} is required.`);
      } else {
        toast.error(`Please provide: ${missingFields.join(", ")}.`);
      }
      return;
    }

    if (formData.features.length === 0) {
      toast.error("Please add at least one feature.");
      return;
    }

    // When creating with workflow path, workflow is required
    if (!editingItem && sourceType === "workflow" && !selectedWorkflowId) {
      toast.error("Please select a workflow for training.");
      return;
    }

    if (!editingItem && sourceType === "workflow" && cronSchedule && !isValidCron(cronSchedule)) {
      toast.error("Invalid cron expression. Expected format: * * * * *");
      return;
    }

    try {
      setLoading(true);
      setError(null);
      setSuccess(null);

      const dataToSubmit = { ...formData };

      // Upload pkl only when sourceType is "upload" and file is selected
      if (
        sourceType === "upload" &&
        selectedFile &&
        (!formData.pkl_file || !formData.pkl_file_id)
      ) {
        const uploadResult = await uploadFile();

        if (!uploadResult) {
          throw new Error("File upload failed");
        }

        dataToSubmit.pkl_file = uploadResult?.file_path;

        // store file manager file ID for download
        if (uploadResult?.file_id) {
          dataToSubmit.pkl_file_id = uploadResult?.file_id;
        }
      }

      if (editingItem) {
        await updateMLModel(editingItem.id, dataToSubmit);
        setSuccess(`ML model "${dataToSubmit.name}" updated successfully`);
      } else {
        dataToSubmit.id = uuidv4();
        const createdModel = await createMLModel(dataToSubmit);
        setSuccess(`ML model "${dataToSubmit.name}" created successfully`);

        // If workflow path: create pipeline config and redirect to detail
        if (sourceType === "workflow" && selectedWorkflowId && createdModel?.id) {
          try {
            await createPipelineConfig(createdModel.id, {
              model_id: createdModel.id,
              workflow_id: selectedWorkflowId,
              cron_schedule: cronSchedule || null,
              is_default: true,
            });
            toast.success("Pipeline configuration added. You can run training from the model detail page.");
            navigate(`/ml-models/${createdModel.id}`);
            return; // Skip cleanup - we navigated away
          } catch (configErr) {
            toast.error("Model created but pipeline config failed. Add it from the model detail page.");
            console.error(configErr);
            navigate(`/ml-models/${createdModel.id}`);
            return;
          }
        }
      }

      setFormData(DEFAULT_FORM_DATA);
      setSelectedFile(null);
      setEditingItem(null);
      setShowForm(false);
      setSourceType("upload");
      setSelectedWorkflowId("");
      setCronSchedule("");
      fetchItems();
    } catch (err) {
      let errorMessage = err instanceof Error ? err.message : String(err);

      if (errorMessage.includes("400")) {
        errorMessage = "An ML model with this name already exists.";
      }

      toast.error(
        `Failed to ${
          editingItem ? "update" : "create"
        } ML model: ${errorMessage}`
      );
    } finally {
      setLoading(false);
    }
  };

  const handleCancel = () => {
    setFormData(DEFAULT_FORM_DATA);
    setSelectedFile(null);
    setEditingItem(null);
    setError(null);
    setSuccess(null);
    setShowForm(false);
    setFeaturesInput("");
    setSourceType("upload");
    setSelectedWorkflowId("");
    setCronSchedule("");
  };

  const handleEdit = (item: MLModel) => {
    setEditingItem(item);
    setFormData({
      ...item,
      features: item.features || [],
    });
    setFeaturesInput((item.features || []).join(', '));
    setSelectedFile(null);
    setShowForm(true);
  };

  const handleDeleteClick = async (id: string, name: string) => {
    setModelToDelete({ id, name });
    setIsDeleteDialogOpen(true);
  };

  const handleDelete = async () => {
    if (!modelToDelete?.id) return;

    try {
      setIsDeleting(true);
      await deleteMLModel(modelToDelete.id);
      toast.success(`ML model deleted successfully.`);
      setItems((prev) => prev.filter((s) => s.id !== modelToDelete.id));
    } catch (err) {
      toast.error("Failed to delete ML model.");
    } finally {
      setModelToDelete(null);
      setIsDeleteDialogOpen(false);
      setIsDeleting(false);
    }
  };

  const downloadModelFile = async (fileId: string) => {
    try {
      const tenantId = localStorage.getItem("tenant_id");
      const fileUrl = getFileDownloadUrl(fileId, getApiUrlString, tenantId || "");
      await downloadFile(fileUrl, `${formData.name || "model"}.pkl`);
    } catch (error) {
      toast.error("Failed to download model file");
      console.error(error);
    }
  };

  const filteredItems = items.filter((item) => {
    const matchesQuery =
      item.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      item.description.toLowerCase().includes(searchQuery.toLowerCase());

    return (
      matchesQuery &&
      (item.model_type === typeFilter || typeFilter === "all")
    );
  });

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

  return (
    <div className="space-y-8">
      {showForm ? (
        <>
          <div className="flex items-center">
            <Button
              variant="ghost"
              size="icon"
              onClick={handleCancel}
              className="mr-2"
            >
              <ChevronLeft className="h-5 w-5" />
            </Button>
            <h2 className="text-2xl font-bold tracking-tight">
              {editingItem ? "Edit ML Model" : "New ML Model"}
            </h2>
          </div>

          {error && (
            <div className="flex items-center gap-2 p-3 text-destructive bg-destructive/10 rounded-md">
              <AlertCircle className="h-4 w-4" />
              <p className="text-sm font-medium">{error}</p>
            </div>
          )}

          {success && (
            <div className="flex items-center gap-2 p-3 text-green-600 bg-green-50 rounded-md">
              <CheckCircle2 className="h-4 w-4" />
              <p className="text-sm font-medium">{success}</p>
            </div>
          )}

          <form onSubmit={handleSubmit}>
            <div className="space-y-6">
              <div className="rounded-lg border bg-white">
                {/* Basic Information */}
                <div className="p-6">
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                    <div>
                      <h3 className="text-lg font-semibold">
                        Basic Information
                      </h3>
                      <p className="text-sm text-gray-500 mt-1">
                        Basic information about the ML model.
                      </p>
                    </div>

                    <div className="md:col-span-2 space-y-6">
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        <div>
                          <div className="mb-1">Name</div>
                          <Input
                            id="name"
                            name="name"
                            value={formData.name}
                            onChange={handleInputChange}
                            placeholder="Name for this ML model"
                          />
                        </div>

                        <div>
                          <div className="mb-1">Model Type</div>
                          <Select
                            value={formData.model_type}
                            onValueChange={(value) =>
                              handleInputChange({
                                target: { name: "model_type", value },
                              } as React.ChangeEvent<HTMLInputElement>)
                            }
                          >
                            <SelectTrigger id="model_type">
                              <SelectValue placeholder="Select model type" />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="xgboost">XGBoost</SelectItem>
                              <SelectItem value="random_forest">Random Forest</SelectItem>
                              <SelectItem value="linear_regression">Linear Regression</SelectItem>
                              <SelectItem value="logistic_regression">Logistic Regression</SelectItem>
                              <SelectItem value="other">Other</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                      </div>

                      <div>
                        <div className="mb-1">Description</div>
                        <Textarea
                          id="description"
                          name="description"
                          value={formData.description}
                          onChange={handleInputChange}
                          placeholder="Brief description of this ML model"
                          rows={3}
                        />
                      </div>

                      <div>
                        <div className="mb-1">Features</div>
                        <Input
                          value={featuresInput}
                          onChange={(e) => handleFeaturesInputChange(e.target.value)}
                          placeholder="Enter features separated by commas (e.g., age, income, credit_score)"
                        />
                        {formData.features.length > 0 && (
                          <p className="text-sm text-gray-500 mt-2">
                            {formData.features.length} feature{formData.features.length !== 1 ? 's' : ''} defined: {formData.features.join(', ')}
                          </p>
                        )}
                      </div>
                    </div>
                  </div>
                </div>

                <div className="-mx-6 my-0 border-t border-gray-200" />

                {/* Model Source - create: radios + upload/workflow; edit: upload only */}
                <div className="p-6">
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                    <div>
                      <h3 className="text-lg font-semibold">Model Source</h3>
                      <p className="text-sm text-gray-500 mt-1">
                        {editingItem ? "Replace the model file if needed." : "How do you want to add this model?"}
                      </p>
                    </div>

                    <div className="md:col-span-2 space-y-6">
                      {!editingItem && (
                        <div>
                          <div className="mb-2">Model Source</div>
                          <div className="flex gap-4">
                            <label className="flex items-center gap-2 cursor-pointer">
                              <input
                                type="radio"
                                name="sourceType"
                                checked={sourceType === "upload"}
                                onChange={() => {
                                  setSourceType("upload");
                                  setSelectedFile(null);
                                }}
                                className="h-4 w-4"
                              />
                              <span className="text-sm font-medium">PKL file</span>
                              <Upload className="h-4 w-4 text-muted-foreground" />
                            </label>
                            <label className="flex items-center gap-2 cursor-pointer">
                              <input
                                type="radio"
                                name="sourceType"
                                checked={sourceType === "workflow"}
                                onChange={() => {
                                  setSourceType("workflow");
                                  setSelectedFile(null);
                                }}
                                className="h-4 w-4"
                              />
                              <span className="text-sm font-medium">Training Workflow</span>
                              <WorkflowIcon className="h-4 w-4 text-muted-foreground" />
                            </label>
                          </div>
                        </div>
                      )}

                      {/* Upload section: show when sourceType is "upload" or when editing */}
                      {(sourceType === "upload" || editingItem) && (
                      <div>
                        <div className="mb-1">Upload Model File (.pkl)</div>
                        <div className="flex flex-col gap-2">
                          <div className="flex items-center justify-center w-full border-2 border-dashed border-border rounded-md cursor-pointer">
                            <label
                              htmlFor="file-upload"
                              className="flex flex-col items-center gap-2 cursor-pointer w-full p-6"
                            >
                              <Upload className="h-10 w-10 text-muted-foreground" />
                              <span className="text-sm font-medium text-muted-foreground">
                                {selectedFile
                                  ? selectedFile.name
                                  : formData.pkl_file_id
                                  ? "Replace file"
                                  : "Select .pkl file to upload (optional)"}
                              </span>
                              <input
                                id="file-upload"
                                type="file"
                                accept=".pkl"
                                onChange={handleFileChange}
                                disabled={isUploading || isAnalyzing}
                                className="hidden"
                              />
                            </label>
                          </div>

                          {selectedFile && (
                            <div className="flex items-center justify-between p-2 bg-muted rounded-md">
                              <div className="flex items-center gap-2">
                                <FileCode className="h-4 w-4" />
                                <span className="text-sm">
                                  {selectedFile.name} (
                                  {(selectedFile.size / 1024).toFixed(1)} KB)
                                </span>
                              </div>
                              <Button
                                type="button"
                                variant="ghost"
                                size="icon"
                                onClick={() => setSelectedFile(null)}
                                className="h-8 w-8"
                              >
                                <X className="h-4 w-4" />
                              </Button>
                            </div>
                          )}

                          {formData.pkl_file_id && !selectedFile && (
                            <div className="flex items-center justify-between p-2 bg-muted rounded-md">
                              <div className="flex items-center gap-2">
                                <FileCode className="h-4 w-4" />
                                <span className="text-sm">
                                  {formData.name}
                                </span>
                              </div>
                              {formData.pkl_file_id && (
                                <Button
                                  type="button"
                                  variant="ghost"
                                  size="icon"
                                  onClick={() => downloadModelFile(formData.pkl_file_id as string)}
                                  className="h-8 w-8 ml-auto"
                                >
                                  <Download className="h-4 w-4" />
                                </Button>
                              )}
                            </div>
                          )}

                          {isUploading && (
                            <div className="p-2 text-sm text-muted-foreground">
                              Uploading file... Please wait.
                            </div>
                          )}
                          {isAnalyzing && (
                            <div className="p-2 text-sm text-muted-foreground">
                              Analyzing file to extract metadata...
                            </div>
                          )}
                        </div>
                      </div>
                      )}

                      {/* Workflow section: show when sourceType is "workflow" and creating */}
                      {!editingItem && sourceType === "workflow" && (
                        <div className="space-y-4 p-4 border rounded-lg bg-gray-50">
                          <div>
                            <Label className="text-sm font-medium mb-2 block">Select Training Workflow</Label>
                            <Select value={selectedWorkflowId} onValueChange={setSelectedWorkflowId}>
                              <SelectTrigger>
                                <SelectValue placeholder="Select a workflow" />
                              </SelectTrigger>
                              <SelectContent>
                                {workflows
                                  .filter((w) => w.nodes?.some((n) => n.type === "trainModelNode"))
                                  .map((workflow) => (
                                    <SelectItem key={workflow.id} value={workflow.id || ""}>
                                      {workflow.name} {workflow.version && `(v${workflow.version})`}
                                    </SelectItem>
                                  ))}
                              </SelectContent>
                            </Select>
                            {workflows.filter((w) => w.nodes?.some((n) => n.type === "trainModelNode")).length === 0 && (
                              <p className="text-sm text-muted-foreground mt-2">
                                No workflows with a Train Model node. Add a Train Model node in the Workflow Studio first.
                              </p>
                            )}
                            <div className="mt-2 flex gap-2">
                              <Button
                                type="button"
                                variant="link"
                                size="sm"
                                className="h-auto p-0"
                                onClick={() => setShowCreateWorkflowDialog(true)}
                              >
                                <Plus className="h-4 w-4 mr-1" />
                                Create New Workflow
                              </Button>
                              <Button
                                type="button"
                                variant="link"
                                size="sm"
                                className="h-auto p-0"
                                onClick={() => window.open("/ai-agents", "_blank")}
                              >
                                <ExternalLink className="h-4 w-4 mr-1" />
                                Open Workflow Studio
                              </Button>
                            </div>
                          </div>
                          <div>
                            <Label className="text-sm font-medium mb-2 block">Cron Schedule (Optional)</Label>
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
                      )}
                    </div>
                  </div>
                </div>

              </div>

              {/* Submit buttons */}
              <div className="flex justify-end gap-3">
                <Button type="button" variant="outline" onClick={handleCancel}>
                  Cancel
                </Button>
                <Button type="submit" disabled={loading || isUploading}>
                  {loading || isUploading
                    ? "Saving..."
                    : editingItem
                    ? "Update ML Model"
                    : "Create ML Model"}
                </Button>
              </div>
            </div>
          </form>
        </>
      ) : (
        <>
          <div className="flex flex-col gap-6">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-3xl font-bold">ML Models</h2>
                <p className="text-zinc-400 font-normal">
                  Manage machine learning model definitions
                </p>
              </div>
              <div className="flex items-center gap-2">
                <div className="relative">
                  <Select
                    value={typeFilter}
                    onValueChange={(value) => setTypeFilter(value)}
                    defaultValue="all"
                  >
                    <SelectTrigger className="min-w-32 bg-white">
                      <SelectValue placeholder="Filter by type" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">(Show all)</SelectItem>
                      <SelectItem value="xgboost">XGBoost</SelectItem>
                      <SelectItem value="random_forest">Random Forest</SelectItem>
                      <SelectItem value="linear_regression">Linear Regression</SelectItem>
                      <SelectItem value="logistic_regression">Logistic Regression</SelectItem>
                      <SelectItem value="other">Other</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <SearchInput
                  placeholder="Search ML models..."
                  className="min-w-64"
                  value={searchQuery}
                  onChange={setSearchQuery}
                />
                <Button
                  onClick={() => {
                    setEditingItem(null);
                    setFormData(DEFAULT_FORM_DATA);
                    setFeaturesInput("");
                    setSourceType("upload");
                    setSelectedWorkflowId("");
                    setCronSchedule("");
                    setSelectedFile(null);
                    setShowForm(true);
                  }}
                  className="rounded-full"
                >
                  <Plus className="h-4 w-4 mr-2" />
                  Add New
                </Button>
              </div>
            </div>

            {error && (
              <div className="flex items-center gap-2 p-3 text-destructive bg-destructive/10 rounded-md">
                <AlertCircle className="h-4 w-4" />
                <p className="text-sm font-medium">{error}</p>
              </div>
            )}

            {success && (
              <div className="flex items-center gap-2 p-3 text-green-600 bg-green-50 rounded-md">
                <CheckCircle2 className="h-4 w-4" />
                <p className="text-sm font-medium">{success}</p>
              </div>
            )}

            <div className="rounded-lg border bg-white overflow-hidden">
              {loading ? (
                <div className="flex justify-center items-center py-12">
                  <div className="text-sm text-gray-500">
                    Loading ML models...
                  </div>
                </div>
              ) : filteredItems.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-12 gap-4 text-center">
                  <Brain className="h-12 w-12 text-gray-400" />
                  <h3 className="font-medium text-lg">No ML models found</h3>
                  <p className="text-sm text-gray-500 max-w-sm">
                    {searchQuery ? "Try adjusting your search query or" : ""}{" "}
                    add your first ML model to start defining your models.
                  </p>
                </div>
              ) : (
                <div className="divide-y divide-gray-100">
                  {filteredItems.map((item) => (
                    <div
                      key={item.id}
                      className="py-4 px-6 hover:bg-gray-50 cursor-pointer transition-colors"
                      onClick={(e) => {
                        if ((e.target as HTMLElement).closest('button')) {
                          return;
                        }
                        navigate(`/ml-models/${item.id}`);
                      }}
                    >
                      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
                        <div className="flex-1 flex flex-col space-y-2">
                          <div className="flex items-center gap-2">
                            <h4 className="text-lg font-semibold">
                              {item.name}
                            </h4>
                            <span className="inline-flex items-center rounded-md bg-blue-100 px-2 py-0.5 text-xs font-bold text-blue-800">
                              {getModelTypeLabel(item.model_type)}
                            </span>
                          </div>
                          <p className="text-sm text-gray-500">
                            {item.description}
                          </p>
                          <div className="flex flex-wrap gap-3 text-sm text-gray-500 mt-1">
                            <span>
                              <strong>Features:</strong> {item.features.length}
                            </span>
                            {!!item.pkl_file_id && (
                              <span className="flex items-center gap-1">
                                <FileCode className="h-4 w-4" />
                                Model file uploaded
                              </span>
                            )}
                            {!item.pkl_file_id && item.pkl_file && (item.pipeline_config_count ?? 0) > 0 && (
                              <span className="flex items-center gap-1">
                                <WorkflowIcon className="h-4 w-4" />
                                Training workflow promoted
                              </span>
                            )}
                          </div>
                        </div>
                        <div className="flex gap-2 justify-center md:justify-end w-full md:w-auto">
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={(e) => {
                              e.stopPropagation();
                              handleEdit(item);
                            }}
                            className="h-8 w-8"
                          >
                            <Pencil className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={(e) => {
                              e.stopPropagation();
                              handleDeleteClick(item.id, item.name);
                            }}
                            className="h-8 w-8 text-red-500"
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </>
      )}

      <ConfirmDialog
        isOpen={isDeleteDialogOpen}
        onOpenChange={setIsDeleteDialogOpen}
        onConfirm={handleDelete}
        isInProgress={isDeleting}
        itemName={modelToDelete?.name || ""}
        description={`This action cannot be undone. This will permanently delete the ML model "${modelToDelete?.name}".`}
      />

      {/* Create New Workflow Dialog */}
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
              After creating, configure the training nodes in the Workflow Studio (AI Agents).
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
    </div>
  );
};

export default MLModelsManager;

