import React, { useState, useEffect } from "react";
import { NlpNodeData } from "../types/nodes";
import { Button } from "@/components/button";
import { RichInput } from "@/components/richInput";
import { Label } from "@/components/label";
import { Save } from "lucide-react";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/select";
import { Switch } from "@/components/switch";
import { NodeConfigPanel } from "../components/NodeConfigPanel";
import { BaseNodeDialogProps } from "./base";
import { DraggableInput } from "../components/custom/DraggableInput";
import { LLMProvider } from "@/interfaces/llmProvider.interface";
import { getAllLLMProviders } from "@/services/llmProviders";
import { useToast } from "@/components/use-toast";
import { LLMProviderDialog } from "@/views/LlmProviders/components/LLMProviderDialog";
import { CreateNewSelectItem } from "@/components/CreateNewSelectItem";
import { useNodeDialogState } from "./useNodeDialogState";

const TASK_OPTIONS = [
  { value: "classify", label: "Classify" },
  { value: "sentiment", label: "Sentiment" },
  { value: "extract", label: "Extract" },
  { value: "summarize", label: "Summarize" },
] as const;
type TaskType = (typeof TASK_OPTIONS)[number]["value"];

const SCALE_OPTIONS = ["1-5", "1-10"] as const;
type ScaleType = (typeof SCALE_OPTIONS)[number];

const STYLE_OPTIONS = ["concise", "bullets", "detailed"] as const;
type StyleType = (typeof STYLE_OPTIONS)[number];

type NlpDialogProps = BaseNodeDialogProps<NlpNodeData, NlpNodeData>;

export const NlpDialog: React.FC<NlpDialogProps> = (props) => {
  const { isOpen, onClose, data } = props;

  const { values, setField, merged, handleSave } =
    useNodeDialogState(
      props,
      () => ({
        name: data.name || "",
        providerId: data.providerId || "",
        inputField: data.inputField ?? "{{source.message}}",
        task: (data.task as TaskType) ?? "classify",
        // classify
        categories: (data.categories ?? []).join(", "),
        multiLabel: data.multiLabel ?? false,
        // sentiment
        scale: (data.scale as ScaleType) ?? "1-5",
        // extract
        schema: data.schema ?? "",
        // summarize
        maxLength: data.maxLength ?? 200,
        style: (data.style as StyleType) ?? "concise",
      }),
      (v) => {
        const parsedCategories = v.categories
          .split(",")
          .map((c) => c.trim())
          .filter((c) => c.length > 0);
        const base = {
          name: v.name,
          providerId: v.providerId,
          inputField: v.inputField,
          task: v.task,
        };
        switch (v.task) {
          case "classify":
            return {
              ...base,
              categories: parsedCategories,
              multiLabel: v.multiLabel,
            };
          case "sentiment":
            return { ...base, scale: v.scale };
          case "extract":
            return { ...base, schema: v.schema };
          case "summarize":
            return { ...base, maxLength: v.maxLength, style: v.style };
          default:
            return base;
        }
      },
    );

  const [availableProviders, setAvailableProviders] = useState<LLMProvider[]>(
    [],
  );
  const { toast } = useToast();
  const [isCreateProviderOpen, setIsCreateProviderOpen] = useState(false);

  const loadProviders = async () => {
    try {
      const providers = await getAllLLMProviders();
      setAvailableProviders(providers.filter((p) => p.is_active === 1));
    } catch {
      toast({
        title: "Error",
        description: "Failed to load LLM providers",
        variant: "destructive",
      });
    }
  };

  useEffect(() => {
    if (isOpen) {
      void loadProviders();
    }
  }, [isOpen]);

  return (
    <>
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
        <div className="space-y-2">
          <Label htmlFor="node-name">Node Name</Label>
          <RichInput
            id="node-name"
            value={values.name}
            onChange={(e) => setField("name", e.target.value)}
            placeholder="Enter the name of this node"
            className="w-full"
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="nlp-provider">LLM Provider</Label>
          <Select
            value={values.providerId || ""}
            onValueChange={(value) => {
              if (value === "__create__") {
                setIsCreateProviderOpen(true);
                return;
              }
              setField("providerId", value);
            }}
          >
            <SelectTrigger id="nlp-provider" className="w-full">
              <SelectValue placeholder="Select an LLM provider" />
            </SelectTrigger>
            <SelectContent>
              {availableProviders.map((provider) => (
                <SelectItem key={provider.id} value={provider.id!}>
                  {provider.name}
                </SelectItem>
              ))}
              <CreateNewSelectItem />
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-2">
          <Label htmlFor="nlp-task">Task</Label>
          <Select
            value={values.task}
            onValueChange={(v) => setField("task", v as TaskType)}
          >
            <SelectTrigger id="nlp-task" className="w-full">
              <SelectValue placeholder="Select a task" />
            </SelectTrigger>
            <SelectContent>
              {TASK_OPTIONS.map((opt) => (
                <SelectItem key={opt.value} value={opt.value}>
                  {opt.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <p className="text-xs text-muted-foreground">
            The text-analysis operation this node performs.
          </p>
        </div>

        <div className="space-y-2">
          <Label htmlFor="nlp-input-field">Input Field</Label>
          <DraggableInput
            id="nlp-input-field"
            value={values.inputField}
            onChange={(e) => setField("inputField", e.target.value)}
            placeholder="{{source.message}}"
            className="w-full"
          />
          <p className="text-xs text-muted-foreground">
            The text to analyze. Supports {"{{variables}}"}.
          </p>
        </div>

        {values.task === "classify" && (
          <>
            <div className="space-y-2">
              <Label htmlFor="nlp-categories">Categories</Label>
              <DraggableInput
                id="nlp-categories"
                value={values.categories}
                onChange={(e) => setField("categories", e.target.value)}
                placeholder="billing, technical, general"
                className="w-full"
              />
              <p className="text-xs text-muted-foreground">
                Comma-separated list of category labels.
              </p>
            </div>

            <div className="flex items-center justify-between rounded-md border p-3 space-x-3">
              <div className="space-y-0.5">
                <Label htmlFor="nlp-multi-label">Multi-label</Label>
                <p className="text-xs text-muted-foreground">
                  Allow the input to be assigned to more than one category.
                </p>
              </div>
              <Switch
                id="nlp-multi-label"
                checked={values.multiLabel}
                onCheckedChange={(checked) =>
                  setField("multiLabel", Boolean(checked))
                }
              />
            </div>
          </>
        )}

        {values.task === "sentiment" && (
          <div className="space-y-2">
            <Label htmlFor="nlp-scale">Scale</Label>
            <Select
              value={values.scale}
              onValueChange={(v) => setField("scale", v as ScaleType)}
            >
              <SelectTrigger id="nlp-scale" className="w-full">
                <SelectValue placeholder="Select scale" />
              </SelectTrigger>
              <SelectContent>
                {SCALE_OPTIONS.map((opt) => (
                  <SelectItem key={opt} value={opt}>
                    {opt}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">
              The numeric range used for the sentiment and urgency scores.
            </p>
          </div>
        )}

        {values.task === "extract" && (
          <div className="space-y-2">
            <Label htmlFor="nlp-schema">Schema</Label>
            <DraggableInput
              id="nlp-schema"
              value={values.schema}
              onChange={(e) => setField("schema", e.target.value)}
              placeholder="order_number, email, plan"
              className="w-full"
            />
            <p className="text-xs text-muted-foreground">
              The entities to extract from the input text.
            </p>
          </div>
        )}

        {values.task === "summarize" && (
          <>
            <div className="space-y-2">
              <Label htmlFor="nlp-max-length">Max Length</Label>
              <RichInput
                id="nlp-max-length"
                type="number"
                min="1"
                value={values.maxLength}
                onChange={(e) => {
                  const parsed = parseInt(e.target.value, 10);
                  setField("maxLength", Number.isNaN(parsed) ? 200 : parsed);
                }}
                placeholder="200"
                className="w-full"
              />
              <p className="text-xs text-muted-foreground">
                Approximate maximum length of the summary.
              </p>
            </div>

            <div className="space-y-2">
              <Label htmlFor="nlp-style">Style</Label>
              <Select
                value={values.style}
                onValueChange={(v) => setField("style", v as StyleType)}
              >
                <SelectTrigger id="nlp-style" className="w-full">
                  <SelectValue placeholder="Select style" />
                </SelectTrigger>
                <SelectContent>
                  {STYLE_OPTIONS.map((opt) => (
                    <SelectItem key={opt} value={opt}>
                      {opt.charAt(0).toUpperCase() + opt.slice(1)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </>
        )}
      </NodeConfigPanel>
      <LLMProviderDialog
        isOpen={isCreateProviderOpen}
        onOpenChange={setIsCreateProviderOpen}
        onProviderSaved={async (provider) => {
          await loadProviders();
          if (provider?.id) {
            setField("providerId", provider.id);
          }
        }}
        mode="create"
      />
    </>
  );
};
