import React, { useEffect, useState } from "react";
import { MLModelInferenceNodeData } from "../types/nodes";
import { Button } from "@/components/button";
import { Label } from "@/components/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/select";
import { Save } from "lucide-react";
import { NodeConfigPanel } from "../components/NodeConfigPanel";
import { BaseNodeDialogProps } from "./base";
import { DraggableInput } from "../components/custom/DraggableInput";
import toast from "react-hot-toast";
import { getAllMLModels } from "@/services/mlModels";
import { MLModel } from "@/interfaces/ml-model.interface";

export const MLModelInferenceDialog: React.FC<
  BaseNodeDialogProps<MLModelInferenceNodeData, MLModelInferenceNodeData>
> = (props) => {
  const { isOpen, onClose, data, onUpdate } = props;

  const [mlModels, setMlModels] = useState<MLModel[]>([]);
  const [selectedModel, setSelectedModel] = useState<MLModel | null>(null);
  const [modelId, setModelId] = useState(data.modelId || "");
  const [inferenceInputs, setInferenceInputs] = useState<
    Record<string, string>
  >(data.inferenceInputs || {});
  const [loading, setLoading] = useState(false);

  // Fetch ML models on mount
  useEffect(() => {
    const fetchModels = async () => {
      try {
        setLoading(true);
        const models = await getAllMLModels();
        setMlModels(models);

        // If there's a selected model ID, find and set it
        if (data.modelId) {
          const model = models.find((m) => m.id === data.modelId);
          if (model) {
            setSelectedModel(model);
          }
        }
      } catch (error) {
        toast.error("Failed to load ML models");
      } finally {
        setLoading(false);
      }
    };

    if (isOpen) {
      fetchModels();
    }
  }, [isOpen, data.modelId]);

  // Update state when data changes
  useEffect(() => {
    setModelId(data.modelId || "");
    setInferenceInputs(data.inferenceInputs || {});
  }, [data, isOpen]);

  // Handle model selection change
  const handleModelChange = (value: string) => {
    setModelId(value);
    const model = mlModels.find((m) => m.id === value);
    setSelectedModel(model || null);

    if (model) {
      // Initialize inference inputs based on model's inference_params
      const newInferenceInputs: Record<string, string> = {};
      if (model.features) {
        model.features.forEach((key) => {
          newInferenceInputs[key] = inferenceInputs[key] || "";
        });
      }
      setInferenceInputs(newInferenceInputs);
    }
  };

  // Update inference input value
  const updateInferenceInput = (key: string, value: string) => {
    setInferenceInputs((prev) => ({
      ...prev,
      [key]: value,
    }));
  };

  // Handle save
  const handleSave = () => {
    if (!modelId) {
      toast.error("Please select an ML model");
      return;
    }

    onUpdate({
      ...data,
      modelId,
      modelName: selectedModel?.name,
      inferenceInputs,
    });
    onClose();
  };

  return (
    <NodeConfigPanel
      footer={
        <>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={handleSave}>
            <Save className="h-4 w-4 mr-2" />
            Save Changes
          </Button>
        </>
      }
      {...props}
      data={{
        ...data,
        modelId,
        inferenceInputs,
      }}
    >
      <div className="space-y-4">
        {/* Model Selection */}
        <div className="space-y-2">
          <Label htmlFor="model">ML Model</Label>
          <Select
            value={modelId}
            onValueChange={handleModelChange}
            disabled={loading}
          >
            <SelectTrigger>
              <SelectValue
                placeholder={
                  loading ? "Loading models..." : "Select an ML model"
                }
              />
            </SelectTrigger>
            <SelectContent>
              {mlModels.map((model) => (
                <SelectItem key={model.id} value={model.id}>
                  <div className="flex items-center gap-2">
                    <span>{model.name}</span>
                    <span className="text-xs text-gray-500">
                      ({model.model_type})
                    </span>
                  </div>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          {selectedModel && (
            <div className="text-xs text-gray-500">
              {selectedModel.description}
            </div>
          )}
        </div>

        {/* Inference Parameters */}
        {selectedModel &&
          selectedModel.features &&
          selectedModel.features.length > 0 && (
            <div className="space-y-2">
              <Label className="text-sm font-semibold">Inference Values</Label>
              <div className="space-y-3 pl-2 border-l-2 border-gray-200">
                {selectedModel.features.map((key) => (
                  <div key={key} className="space-y-1">
                    <Label
                      htmlFor={`param-${key}`}
                      className="text-xs text-gray-600"
                    >
                      {key}
                    </Label>
                    <DraggableInput
                      id={`param-${key}`}
                      value={inferenceInputs[key] || ""}
                      onChange={(e) =>
                        updateInferenceInput(key, e.target.value)
                      }
                      placeholder={`Add value`}
                      className="text-sm"
                    />
                    <div className="text-xs text-gray-400">
                      Use {"{{variable}}"} for dynamic values
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

        {!selectedModel && !loading && (
          <div className="text-sm text-gray-500 text-center py-4">
            Select an ML model to configure inference parameters
          </div>
        )}
      </div>
    </NodeConfigPanel>
  );
};
