import React, { useState, useEffect } from "react";
import { RouterNodeData } from "../types/nodes";
import { useNodeDialogState } from "./useNodeDialogState";
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
import { NodeConfigPanel } from "../components/NodeConfigPanel";
import { BaseNodeDialogProps } from "./base";
import { DraggableInput } from "../components/custom/DraggableInput";
import { DraggableTextArea } from "../components/custom/DraggableTextArea";
import { Switch } from "@/components/switch";
import { LLMProvider } from "@/interfaces/llmProvider.interface";
import { getAllLLMProviders } from "@/services/llmProviders";
import { useToast } from "@/components/use-toast";
import { LLMProviderDialog } from "@/views/LlmProviders/components/LLMProviderDialog";
import { CreateNewSelectItem } from "@/components/CreateNewSelectItem";
import { useWorkflow } from "../context/WorkflowContext";
import { PromptEditorButton } from "../components/PromptEditor/PromptEditorButton";

const CONDITION_OPTIONS = [
  "equal",
  "not_equal",
  "contains",
  "not_contain",
  "starts_with",
  "not_starts_with",
  "ends_with",
  "not_ends_with",
  "regex",
] as const;

type ConditionType = (typeof CONDITION_OPTIONS)[number];

const FALLBACK_ROUTE_OPTIONS = [
  { value: "false", label: "false" },
  { value: "true", label: "true" },
] as const;

function isSmartModeEnabledValue(
  v: boolean | string | undefined | null,
): boolean {
  if (v === true) return true;
  if (v === false || v === undefined || v === null) return false;
  if (typeof v === "string") return v.trim().toLowerCase() === "true";
  return false;
}

type RouterDialogProps = BaseNodeDialogProps<RouterNodeData, RouterNodeData>;

export const RouterDialog: React.FC<RouterDialogProps> = (props) => {
  const { isOpen, onClose, data } = props;

  const { values, setField, merged, handleSave } = useNodeDialogState(
    props,
    () => ({
      name: data.name || "",
      smartModeEnabled: isSmartModeEnabledValue(data.smartModeEnabled),
      providerId: data.providerId || "",
      smartPrompt: data.smartPrompt || "",
      systemPrompt: data.systemPrompt || "",
      fallbackRoute: data.fallbackRoute === "true" ? "true" : "false",
      firstValue: data.first_value ?? "",
      compareCondition: (data.compare_condition as ConditionType) ?? "contains",
      secondValue: data.second_value ?? "",
    }),
    (v) => {
      const normalizedFallback =
        v.fallbackRoute === "true" || v.fallbackRoute === "false"
          ? v.fallbackRoute
          : "false";
      return {
        name: v.name,
        smartModeEnabled: v.smartModeEnabled,
        providerId: v.providerId,
        smartPrompt: v.smartPrompt,
        systemPrompt: v.systemPrompt,
        fallbackRoute: normalizedFallback,
        first_value: v.firstValue,
        compare_condition: v.compareCondition,
        second_value: v.secondValue,
      };
    },
  );

  const [availableProviders, setAvailableProviders] = useState<LLMProvider[]>(
    [],
  );
  const { toast } = useToast();
  const [isCreateProviderOpen, setIsCreateProviderOpen] = useState(false);
  const { workflow } = useWorkflow();

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
  }, [isOpen, data]);

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

        <div className="flex items-center justify-between rounded-md border p-3 space-x-3">
          <div className="space-y-0.5">
            <Label htmlFor="smart-mode">Smart Mode</Label>
            <p className="text-xs text-muted-foreground">
              Use an LLM to choose the true or false branch from a prompt,
              instead of comparing values.
            </p>
          </div>
          <Switch
            id="smart-mode"
            checked={values.smartModeEnabled}
            onCheckedChange={(checked) =>
              setField("smartModeEnabled", Boolean(checked))
            }
          />
        </div>

        {!values.smartModeEnabled && (
          <>
            <div className="space-y-2">
              <Label htmlFor="path_name">First Value</Label>
              <DraggableInput
                id="path_name"
                value={values.firstValue}
                onChange={(e) => setField("firstValue", e.target.value)}
                placeholder="first value to compare"
                className="w-full"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="compare_condition">Compare Condition</Label>
              <Select
                value={values.compareCondition}
                onValueChange={(value) =>
                  setField("compareCondition", value as ConditionType)
                }
              >
                <SelectTrigger id="compare_condition">
                  <SelectValue placeholder="Select condition" />
                </SelectTrigger>
                <SelectContent>
                  {CONDITION_OPTIONS.map((opt) => (
                    <SelectItem key={opt} value={opt}>
                      {opt.replace(/_/g, " ")}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="value_condition">Second Value</Label>
              <DraggableInput
                id="value_condition"
                value={values.secondValue}
                onChange={(e) => setField("secondValue", e.target.value)}
                placeholder="second value to compare"
                className="w-full"
              />
            </div>
          </>
        )}

        {values.smartModeEnabled && (
          <>
            <div className="space-y-2">
              <Label htmlFor="router-provider">LLM Provider</Label>
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
                <SelectTrigger id="router-provider" className="w-full">
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
              <p className="text-xs text-muted-foreground">
                Model used to decide between the true and false outputs.
              </p>
            </div>

            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label htmlFor="router-system-prompt">System Prompt</Label>
                {workflow?.id && props.nodeId && (
                  <PromptEditorButton
                    workflowId={workflow.id}
                    nodeId={props.nodeId}
                    promptField="systemPrompt"
                    currentValue={values.systemPrompt}
                    onPromptChange={(val) => setField("systemPrompt", val)}
                    defaultProviderId={values.providerId}
                  />
                )}
              </div>
              <DraggableTextArea
                id="router-system-prompt"
                value={values.systemPrompt}
                onChange={(e) => setField("systemPrompt", e.target.value)}
                placeholder="Optional. Leave empty to use the built-in routing instructions."
                className="w-full min-h-[100px] text-sm"
              />
            </div>

            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label htmlFor="router-smart-prompt">Routing prompt</Label>
                {workflow?.id && props.nodeId && (
                  <PromptEditorButton
                    workflowId={workflow.id}
                    nodeId={props.nodeId}
                    promptField="smartPrompt"
                    currentValue={values.smartPrompt}
                    onPromptChange={(val) => setField("smartPrompt", val)}
                    defaultProviderId={values.providerId}
                  />
                )}
              </div>
              <DraggableTextArea
                id="router-smart-prompt"
                value={values.smartPrompt}
                onChange={(e) => setField("smartPrompt", e.target.value)}
                placeholder="Describe when the workflow should take the true branch. The model must answer only true or false."
                className="w-full min-h-[120px] text-sm"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="router-fallback">Fallback route</Label>
              <Select
                value={values.fallbackRoute}
                onValueChange={(v) =>
                  setField("fallbackRoute", v === "true" ? "true" : "false")
                }
              >
                <SelectTrigger id="router-fallback" className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {FALLBACK_ROUTE_OPTIONS.map((opt) => (
                    <SelectItem key={opt.value} value={opt.value}>
                      {opt.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <p className="text-xs text-muted-foreground">
                If the provider, prompt, or model output is invalid, this branch
                is used.
              </p>
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
