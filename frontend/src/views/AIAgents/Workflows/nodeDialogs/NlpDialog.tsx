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
  const { isOpen, onClose, data, onUpdate } = props;

  const [name, setName] = useState(data.name || "");
  const [providerId, setProviderId] = useState(data.providerId || "");
  const [inputField, setInputField] = useState(
    data.inputField ?? "{{source.message}}",
  );
  const [task, setTask] = useState<TaskType>(
    (data.task as TaskType) ?? "classify",
  );

  // classify
  const [categories, setCategories] = useState(
    (data.categories ?? []).join(", "),
  );
  const [multiLabel, setMultiLabel] = useState(data.multiLabel ?? false);
  // sentiment
  const [scale, setScale] = useState<ScaleType>(
    (data.scale as ScaleType) ?? "1-5",
  );
  // extract
  const [schema, setSchema] = useState(data.schema ?? "");
  // summarize
  const [maxLength, setMaxLength] = useState<number>(data.maxLength ?? 200);
  const [style, setStyle] = useState<StyleType>(
    (data.style as StyleType) ?? "concise",
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
      setName(data.name || "");
      setProviderId(data.providerId || "");
      setInputField(data.inputField ?? "{{source.message}}");
      setTask((data.task as TaskType) ?? "classify");
      setCategories((data.categories ?? []).join(", "));
      setMultiLabel(data.multiLabel ?? false);
      setScale((data.scale as ScaleType) ?? "1-5");
      setSchema(data.schema ?? "");
      setMaxLength(data.maxLength ?? 200);
      setStyle((data.style as StyleType) ?? "concise");
      void loadProviders();
    }
  }, [isOpen, data]);

  const parsedCategories = categories
    .split(",")
    .map((c) => c.trim())
    .filter((c) => c.length > 0);

  const buildData = (): NlpNodeData => {
    const base: NlpNodeData = {
      ...data,
      name,
      providerId,
      inputField,
      task,
    };
    switch (task) {
      case "classify":
        return { ...base, categories: parsedCategories, multiLabel };
      case "sentiment":
        return { ...base, scale };
      case "extract":
        return { ...base, schema };
      case "summarize":
        return { ...base, maxLength, style };
      default:
        return base;
    }
  };

  const handleSave = () => {
    onUpdate(buildData());
    onClose();
  };

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
        data={buildData()}
      >
        <div className="space-y-2">
          <Label htmlFor="node-name">Node Name</Label>
          <RichInput
            id="node-name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Enter the name of this node"
            className="w-full"
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="nlp-provider">LLM Provider</Label>
          <Select
            value={providerId || ""}
            onValueChange={(value) => {
              if (value === "__create__") {
                setIsCreateProviderOpen(true);
                return;
              }
              setProviderId(value);
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
          <Select value={task} onValueChange={(v) => setTask(v as TaskType)}>
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
          <p className="text-xs text-gray-500">
            The text-analysis operation this node performs.
          </p>
        </div>

        <div className="space-y-2">
          <Label htmlFor="nlp-input-field">Input Field</Label>
          <DraggableInput
            id="nlp-input-field"
            value={inputField}
            onChange={(e) => setInputField(e.target.value)}
            placeholder="{{source.message}}"
            className="w-full"
          />
          <p className="text-xs text-gray-500">
            The text to analyze. Supports {"{{variables}}"}.
          </p>
        </div>

        {task === "classify" && (
          <>
            <div className="space-y-2">
              <Label htmlFor="nlp-categories">Categories</Label>
              <DraggableInput
                id="nlp-categories"
                value={categories}
                onChange={(e) => setCategories(e.target.value)}
                placeholder="billing, technical, general"
                className="w-full"
              />
              <p className="text-xs text-gray-500">
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
                checked={multiLabel}
                onCheckedChange={(checked) => setMultiLabel(Boolean(checked))}
              />
            </div>
          </>
        )}

        {task === "sentiment" && (
          <div className="space-y-2">
            <Label htmlFor="nlp-scale">Scale</Label>
            <Select value={scale} onValueChange={(v) => setScale(v as ScaleType)}>
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
            <p className="text-xs text-gray-500">
              The numeric range used for the sentiment and urgency scores.
            </p>
          </div>
        )}

        {task === "extract" && (
          <div className="space-y-2">
            <Label htmlFor="nlp-schema">Schema</Label>
            <DraggableInput
              id="nlp-schema"
              value={schema}
              onChange={(e) => setSchema(e.target.value)}
              placeholder="order_number, email, plan"
              className="w-full"
            />
            <p className="text-xs text-gray-500">
              The entities to extract from the input text.
            </p>
          </div>
        )}

        {task === "summarize" && (
          <>
            <div className="space-y-2">
              <Label htmlFor="nlp-max-length">Max Length</Label>
              <RichInput
                id="nlp-max-length"
                type="number"
                min="1"
                value={maxLength}
                onChange={(e) => {
                  const parsed = parseInt(e.target.value, 10);
                  setMaxLength(Number.isNaN(parsed) ? 200 : parsed);
                }}
                placeholder="200"
                className="w-full"
              />
              <p className="text-xs text-gray-500">
                Approximate maximum length of the summary.
              </p>
            </div>

            <div className="space-y-2">
              <Label htmlFor="nlp-style">Style</Label>
              <Select
                value={style}
                onValueChange={(v) => setStyle(v as StyleType)}
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
            setProviderId(provider.id);
          }
        }}
        mode="create"
      />
    </>
  );
};
