import React, { useEffect, useState } from "react";
import { SwitchCase, SwitchMatchMode, SwitchNodeData } from "../types/nodes";
import { useNodeDialogState } from "./useNodeDialogState";
import { Button } from "@/components/button";
import { RichInput } from "@/components/richInput";
import { Label } from "@/components/label";
import { Plus, Save, Trash2 } from "lucide-react";
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
import { DraggableTextArea } from "../components/custom/DraggableTextArea";
import { LLMProvider } from "@/interfaces/llmProvider.interface";
import { getAllLLMProviders } from "@/services/llmProviders";
import { useToast } from "@/components/use-toast";
import { LLMProviderDialog } from "@/views/LlmProviders/components/LLMProviderDialog";
import { CreateNewSelectItem } from "@/components/CreateNewSelectItem";
import { useWorkflow } from "../context/WorkflowContext";
import { PromptEditorButton } from "../components/PromptEditor/PromptEditorButton";
import {
  buildSwitchHandlers,
  isSwitchSmartMode,
  nextSwitchCaseId,
  SWITCH_MATCH_MODE_LABELS,
} from "../nodeTypes/router/switchCases";

const MATCH_MODE_OPTIONS = Object.keys(
  SWITCH_MATCH_MODE_LABELS
) as SwitchMatchMode[];

type SwitchDialogProps = BaseNodeDialogProps<SwitchNodeData, SwitchNodeData>;

export const SwitchDialog: React.FC<SwitchDialogProps> = (props) => {
  const { isOpen, onClose, data } = props;

  const { values, setField, merged, handleSave } = useNodeDialogState(
    props,
    () => ({
      name: data.name || "",
      smartModeEnabled: isSwitchSmartMode(data.smartModeEnabled),
      providerId: data.providerId || "",
      smartPrompt: data.smartPrompt || "",
      systemPrompt: data.systemPrompt || "",
      switchValue: data.switchValue ?? "",
      matchMode: data.matchMode ?? "equal",
      caseSensitive: data.caseSensitive ?? false,
      cases: data.cases ?? [],
    }),
    (v) => ({
      name: v.name,
      smartModeEnabled: v.smartModeEnabled,
      providerId: v.providerId,
      smartPrompt: v.smartPrompt,
      systemPrompt: v.systemPrompt,
      switchValue: v.switchValue,
      matchMode: v.matchMode,
      caseSensitive: v.caseSensitive,
      cases: v.cases,
      handlers: buildSwitchHandlers(v.cases),
    })
  );

  const [availableProviders, setAvailableProviders] = useState<LLMProvider[]>(
    []
  );
  const [isCreateProviderOpen, setIsCreateProviderOpen] = useState(false);
  const { toast } = useToast();
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

  const updateCase = (caseId: string, patch: Partial<SwitchCase>) =>
    setField(
      "cases",
      values.cases.map((c) => (c.id === caseId ? { ...c, ...patch } : c))
    );

  const addCase = () => {
    const id = nextSwitchCaseId(values.cases);
    setField("cases", [
      ...values.cases,
      { id, label: `Case ${values.cases.length + 1}`, value: "" },
    ]);
  };

  const removeCase = (caseId: string) =>
    setField(
      "cases",
      values.cases.filter((c) => c.id !== caseId)
    );

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
            <Label htmlFor="switch-smart-mode">Smart Mode</Label>
            <p className="text-xs text-muted-foreground">
              Use an LLM to choose the case from a prompt, instead of comparing
              a value.
            </p>
          </div>
          <Switch
            id="switch-smart-mode"
            checked={values.smartModeEnabled}
            onCheckedChange={(checked) =>
              setField("smartModeEnabled", Boolean(checked))
            }
          />
        </div>

        {!values.smartModeEnabled && (
          <>
            <div className="space-y-2">
              <Label htmlFor="switch-value">Value</Label>
              <DraggableInput
                id="switch-value"
                value={values.switchValue}
                onChange={(e) => setField("switchValue", e.target.value)}
                placeholder="e.g. the category returned by a Classifier node"
                className="w-full"
              />
              <p className="text-sm text-muted-foreground">
                The single value compared against every case, usually a
                variable from an upstream node.
              </p>
            </div>

            <div className="space-y-2">
              <Label htmlFor="switch-match-mode">Match Mode</Label>
              <Select
                value={values.matchMode}
                onValueChange={(value) =>
                  setField("matchMode", value as SwitchMatchMode)
                }
              >
                <SelectTrigger id="switch-match-mode">
                  <SelectValue placeholder="Select match mode" />
                </SelectTrigger>
                <SelectContent>
                  {MATCH_MODE_OPTIONS.map((mode) => (
                    <SelectItem key={mode} value={mode}>
                      {SWITCH_MATCH_MODE_LABELS[mode]}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="flex items-center justify-between rounded-md border p-3 space-x-3">
              <div className="space-y-0.5">
                <Label htmlFor="switch-case-sensitive">Case sensitive</Label>
                <p className="text-xs text-muted-foreground">
                  When off, "Billing" and "billing" match the same case.
                </p>
              </div>
              <Switch
                id="switch-case-sensitive"
                checked={values.caseSensitive}
                onCheckedChange={(checked) =>
                  setField("caseSensitive", Boolean(checked))
                }
              />
            </div>
          </>
        )}

        {values.smartModeEnabled && (
          <>
            <div className="space-y-2">
              <Label htmlFor="switch-provider">LLM Provider</Label>
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
                <SelectTrigger id="switch-provider" className="w-full">
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
                Model used to choose between the cases.
              </p>
            </div>

            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label htmlFor="switch-system-prompt">System Prompt</Label>
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
                id="switch-system-prompt"
                size="body"
                value={values.systemPrompt}
                onChange={(e) => setField("systemPrompt", e.target.value)}
                placeholder="Optional. Leave empty to use the built-in routing instructions."
                className="w-full text-sm"
              />
            </div>

            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label htmlFor="switch-smart-prompt">Routing prompt</Label>
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
                id="switch-smart-prompt"
                size="body"
                value={values.smartPrompt}
                onChange={(e) => setField("smartPrompt", e.target.value)}
                placeholder="Describe what to route on, e.g. the customer's message. The cases below are added as the routes the model can choose."
                className="w-full text-sm"
              />
              <p className="text-xs text-muted-foreground">
                If the provider, prompt, or model answer is invalid, the Default
                branch is used.
              </p>
            </div>
          </>
        )}

        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <Label>Cases</Label>
            <Button type="button" variant="outline" size="sm" onClick={addCase}>
              <Plus className="h-4 w-4 mr-1" />
              Add Case
            </Button>
          </div>
          <p className="text-sm text-muted-foreground">
            {values.smartModeEnabled
              ? "The model picks one case using each case's name and description. Each case gets its own output on the node, in this order."
              : "Cases are evaluated top to bottom; the first match wins. Each case gets its own output on the node, in this order."}
          </p>

          <div className="space-y-2">
            {values.cases.map((switchCase, index) => (
              <div
                key={switchCase.id}
                className="flex items-center gap-2 rounded-md border p-2"
              >
                <span className="flex h-6 min-w-6 shrink-0 items-center justify-center rounded bg-muted px-1 text-xs font-medium text-muted-foreground">
                  {index + 1}
                </span>
                <RichInput
                  aria-label={`Case ${index + 1} name`}
                  value={switchCase.label}
                  onChange={(e) =>
                    updateCase(switchCase.id, { label: e.target.value })
                  }
                  placeholder="Branch name"
                  className="flex-1"
                />
                <RichInput
                  aria-label={`Case ${index + 1} ${
                    values.smartModeEnabled ? "description" : "value"
                  }`}
                  value={switchCase.value}
                  onChange={(e) =>
                    updateCase(switchCase.id, { value: e.target.value })
                  }
                  placeholder={
                    values.smartModeEnabled
                      ? "When to choose this case"
                      : "Value to match"
                  }
                  className={`flex-1 ${values.smartModeEnabled ? "" : "font-mono"}`}
                />
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="shrink-0 text-red-600 hover:text-red-700"
                  onClick={() => removeCase(switchCase.id)}
                  title="Remove case"
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            ))}

            <div className="flex items-center gap-2 rounded-md border border-dashed p-2">
              <span className="flex h-6 min-w-6 shrink-0 items-center justify-center rounded border border-dashed border-muted-foreground/40 px-1 text-xs text-muted-foreground">
                ∗
              </span>
              <div className="flex-1 text-sm">
                <span className="font-medium">Default</span>
                <span className="text-muted-foreground">
                  {" "}
                  — taken when no case {values.smartModeEnabled ? "is chosen" : "matches"}
                </span>
              </div>
            </div>
          </div>
        </div>
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
