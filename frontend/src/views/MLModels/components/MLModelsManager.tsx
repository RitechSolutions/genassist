import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "react-hot-toast";
import {
  getAllMLModels,
  createMLModel,
  updateMLModel,
  deleteMLModel,
  uploadModelFile,
} from "@/services/mlModels";
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
} from "lucide-react";
import { SearchInput } from "@/components/SearchInput";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { MLModel } from "@/interfaces/ml-model.interface";
import { Badge } from "@/components/badge";

const DEFAULT_FORM_DATA: MLModel = {
  id: uuidv4(),
  name: "",
  description: "",
  model_type: "xgboost",
  pkl_file: null,
  features: [],
  target_variable: "",
  inference_params: {},
};

const MLModelsManager: React.FC = () => {
  const navigate = useNavigate();
  const [items, setItems] = useState<MLModel[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState<boolean>(false);
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
  const [inferenceParamsKV, setInferenceParamsKV] = useState<
    { key: string; value: string }[]
  >([]);

  useEffect(() => {
    fetchItems();
  }, []);

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

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0] || null;
    setSelectedFile(file);
  };

  const uploadFile = async () => {
    if (!selectedFile) return null;

    setIsUploading(true);

    try {
      const result = await uploadModelFile(selectedFile);
      return result;
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

  const syncInferenceParamsToForm = (kv: { key: string; value: string }[]) => {
    const paramsObject = kv.reduce((acc, { key, value }) => {
      const trimmedKey = key.trim();
      if (trimmedKey.length > 0) {
        acc[trimmedKey] = value;
      }
      return acc;
    }, {} as Record<string, string>);
    setFormData((prev) => ({
      ...prev,
      inference_params: paramsObject,
    }));
  };

  const addParamRow = () => {
    setInferenceParamsKV((prev) => {
      const next = [...prev, { key: "", value: "" }];
      syncInferenceParamsToForm(next);
      return next;
    });
  };

  const updateParamKey = (index: number, newKey: string) => {
    setInferenceParamsKV((prev) => {
      const next = prev.map((item, i) => (i === index ? { ...item, key: newKey } : item));
      syncInferenceParamsToForm(next);
      return next;
    });
  };

  const updateParamValue = (index: number, newValue: string) => {
    setInferenceParamsKV((prev) => {
      const next = prev.map((item, i) => (i === index ? { ...item, value: newValue } : item));
      syncInferenceParamsToForm(next);
      return next;
    });
  };

  const removeParamRow = (index: number) => {
    setInferenceParamsKV((prev) => {
      const next = prev.filter((_, i) => i !== index);
      syncInferenceParamsToForm(next);
      return next;
    });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    const requiredFields = [
      { label: "name", isEmpty: !formData.name },
      { label: "description", isEmpty: !formData.description },
      { label: "model type", isEmpty: !formData.model_type },
      { label: "target variable", isEmpty: !formData.target_variable },
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

    try {
      setLoading(true);
      setError(null);
      setSuccess(null);

      const dataToSubmit = { ...formData };

      if (selectedFile && !formData.pkl_file) {
        const uploadResult = await uploadFile();

        if (!uploadResult) {
          throw new Error("File upload failed");
        }

        dataToSubmit.pkl_file = uploadResult.file_path;
      }

      if (editingItem) {
        await updateMLModel(editingItem.id, dataToSubmit);
        setSuccess(`ML model "${dataToSubmit.name}" updated successfully`);
      } else {
        dataToSubmit.id = uuidv4();
        await createMLModel(dataToSubmit);
        setSuccess(`ML model "${dataToSubmit.name}" created successfully`);
      }

      setFormData(DEFAULT_FORM_DATA);
      setSelectedFile(null);
      setEditingItem(null);
      setShowForm(false);
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
    setInferenceParamsKV([]);
  };

  const handleEdit = (item: MLModel) => {
    setEditingItem(item);
    setFormData({
      ...item,
      features: item.features || [],
      inference_params: item.inference_params || {},
    });
    setFeaturesInput((item.features || []).join(', '));
    setInferenceParamsKV(
      Object.entries(item.inference_params || {}).map(([key, value]) => ({
        key,
        value: String(value ?? ""),
      }))
    );
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
                        <div className="mb-1">Target Variable</div>
                        <Input
                          id="target_variable"
                          name="target_variable"
                          value={formData.target_variable}
                          onChange={handleInputChange}
                          placeholder="e.g., price, category, churn"
                        />
                      </div>

                      <div>
                        <div className="mb-1">Upload Model File (.pkl)</div>
                        <div className="flex flex-col gap-2">
                          <div className="flex items-center justify-center w-full border-2 border-dashed border-border rounded-md p-6">
                            <label
                              htmlFor="file-upload"
                              className="flex flex-col items-center gap-2 cursor-pointer"
                            >
                              <Upload className="h-10 w-10 text-muted-foreground" />
                              <span className="text-sm font-medium text-muted-foreground">
                                {selectedFile
                                  ? selectedFile.name
                                  : formData.pkl_file
                                  ? "Replace file"
                                  : "Select .pkl file to upload (optional)"}
                              </span>
                              <input
                                id="file-upload"
                                type="file"
                                accept=".pkl"
                                onChange={handleFileChange}
                                disabled={isUploading}
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

                          {formData.pkl_file && !selectedFile && (
                            <div className="flex items-center justify-between p-2 bg-muted rounded-md">
                              <div className="flex items-center gap-2">
                                <FileCode className="h-4 w-4" />
                                <span className="text-sm">
                                  File: {formData.pkl_file}
                                </span>
                              </div>
                            </div>
                          )}

                          {isUploading && (
                            <div className="p-2 text-sm text-muted-foreground">
                              Uploading file... Please wait.
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                </div>

                <div className="-mx-6 my-0 border-t border-gray-200" />

                {/* Features Section */}
                <div className="p-6">
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                    <div>
                      <h3 className="text-lg font-semibold">Features</h3>
                      <p className="text-sm text-gray-500 mt-1">
                        Enter comma-separated feature names for the model.
                      </p>
                    </div>

                    <div className="md:col-span-2 space-y-4">
                      <div>
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

                {/* Inference Parameters Section */}
                <div className="p-6">
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                    <div>
                      <h3 className="text-lg font-semibold">
                        Inference Parameters
                      </h3>
                      <p className="text-sm text-gray-500 mt-1">
                        Define parameter names and their default values for inference.
                      </p>
                    </div>

                    <div className="md:col-span-2 space-y-4">
                      <div className="space-y-3">
                        {inferenceParamsKV.length === 0 && (
                          <p className="text-sm text-gray-500">No parameters defined yet.</p>
                        )}
                        {inferenceParamsKV.map((item, index) => (
                          <div key={index} className="grid grid-cols-12 gap-2 items-center">
                            <div className="col-span-5">
                              <Input
                                value={item.key}
                                onChange={(e) => updateParamKey(index, e.target.value)}
                                placeholder="Parameter name (e.g., temperature)"
                              />
                            </div>
                            <div className="col-span-6">
                              <Input
                                value={item.value}
                                onChange={(e) => updateParamValue(index, e.target.value)}
                                placeholder="Default value (optional)"
                              />
                            </div>
                            <div className="col-span-1 flex justify-end">
                              <Button
                                type="button"
                                variant="ghost"
                                size="icon"
                                onClick={() => removeParamRow(index)}
                                className="h-8 w-8 text-red-500"
                              >
                                <Trash2 className="h-4 w-4" />
                              </Button>
                            </div>
                          </div>
                        ))}
                        <div>
                          <Button type="button" variant="secondary" onClick={addParamRow}>
                            <Plus className="h-4 w-4 mr-2" />
                            Add Parameter
                          </Button>
                        </div>
                      </div>
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
                <Button onClick={() => setShowForm(true)} className="rounded-full">
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
                        // Don't navigate if clicking on buttons
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
                              <strong>Target:</strong> {item.target_variable}
                            </span>
                            <span>
                              <strong>Features:</strong> {item.features.length}
                            </span>
                            {item.pkl_file && (
                              <span className="flex items-center gap-1">
                                <FileCode className="h-4 w-4" />
                                Model file uploaded
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
    </div>
  );
};

export default MLModelsManager;

