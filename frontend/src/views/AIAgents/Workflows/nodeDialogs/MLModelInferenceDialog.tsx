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
import { useNodeDialogState } from "./useNodeDialogState";

export const MLModelInferenceDialog: React.FC<
  BaseNodeDialogProps<MLModelInferenceNodeData, MLModelInferenceNodeData>
> = (props) => {
  const { isOpen, onClose, data } = props;

  const [mlModels, setMlModels] = useState<MLModel[]>([]);
  const [selectedModel, setSelectedModel] = useState<MLModel | null>(null);
  const [loading, setLoading] = useState(false);

  const { values, setField, setValues, merged, handleSave: saveNode } =
    useNodeDialogState(
      props,
      () => ({
        modelId: data.modelId || "",
        inferenceInputs: data.inferenceInputs || {},
      }),
      (v) => ({
        modelId: v.modelId,
        modelName: selectedModel?.name,
        inferenceInputs: v.inferenceInputs,
      }),
    );

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

  // Handle model selection change
  const handleModelChange = (value: string) => {
    setField("modelId", value);
    const model = mlModels.find((m) => m.id === value);
    setSelectedModel(model || null);

    if (model) {
      // Initialize inference inputs based on the model's features
      const newInferenceInputs: Record<string, string> = {};
      if (model.features) {
        model.features.forEach((key) => {
          newInferenceInputs[key] = values.inferenceInputs[key] || "";
        });
      }
      setField("inferenceInputs", newInferenceInputs);
    }
  };

  // Update inference input value
  const updateInferenceInput = (key: string, value: string) => {
    setValues((prev) => ({
      ...prev,
      inferenceInputs: {
        ...prev.inferenceInputs,
        [key]: value,
      },
    }));
  };

  // Handle save
  const handleSave = () => {
    if (!values.modelId) {
      toast.error("Please select an ML model");
      return;
    }

    saveNode();
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
      data={merged}
    >
      <div className="space-y-4">
        {/* Model Selection */}
        <div className="space-y-2">
          <Label htmlFor="model">ML Model</Label>
          <Select
            value={values.modelId}
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
                    <span className="text-xs text-muted-foreground">
                      ({model.model_type})
                    </span>
                  </div>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          {selectedModel && (
            <div className="text-xs text-muted-foreground">
              {selectedModel.description}
            </div>
          )}
        </div>

        {/* Inference Values */}
        {selectedModel &&
          selectedModel.features &&
          selectedModel.features.length > 0 && (
            <div className="space-y-2">
              <Label className="text-sm font-semibold">Inference Values</Label>
              <div className="space-y-3 pl-2 border-l-2 border-border">
                {selectedModel.features.map((key) => (
                  <div key={key} className="space-y-1">
                    <Label
                      htmlFor={`param-${key}`}
                      className="text-xs text-muted-foreground"
                    >
                      {key}
                    </Label>
                    <DraggableInput
                      id={`param-${key}`}
                      value={values.inferenceInputs[key] || ""}
                      onChange={(e) =>
                        updateInferenceInput(key, e.target.value)
                      }
                      placeholder={`Add value`}
                      className="text-sm"
                    />
                    <div className="text-xs text-muted-foreground">
                      Use {"{{variable}}"} for dynamic values
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

        {!selectedModel && !loading && (
          <div className="text-sm text-muted-foreground text-center py-4">
            Select an ML model to configure Inference Values
          </div>
        )}
      </div>
    </NodeConfigPanel>
  );
};
