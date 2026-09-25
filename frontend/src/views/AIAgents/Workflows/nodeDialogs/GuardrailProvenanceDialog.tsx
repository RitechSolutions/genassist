import React, { useEffect } from "react";
import { RichInput } from "@/components/richInput";
import { Label } from "@/components/label";
import { Switch } from "@/components/switch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/select";
import { useQuery } from "@tanstack/react-query";
import { getAllLLMProviders } from "@/services/llmProviders";
import { LLMProvider } from "@/interfaces/llmProvider.interface";
import { BaseNodeDialogProps } from "./base";
import { GuardrailProvenanceNodeData } from "../types/nodes";
import { NodeConfigPanel } from "../components/NodeConfigPanel";
import { DraggableTextArea } from "../components/custom/DraggableTextArea";
import { useWorkflow } from "../context/WorkflowContext";
import { PromptEditorButton } from "../components/PromptEditor/PromptEditorButton";
import { useNodeDialogState } from "./useNodeDialogState";

type Props = BaseNodeDialogProps<
  GuardrailProvenanceNodeData,
  GuardrailProvenanceNodeData
>;

export const GuardrailProvenanceDialog: React.FC<Props> = (props) => {
  const { isOpen, onClose, data } = props;
  const { workflow } = useWorkflow();

  const { values, setValues, setField, merged, handleSave } =
    useNodeDialogState(props, () => data);

  const { data: providers = [] } = useQuery({
    queryKey: ["llmProviders"],
    queryFn: getAllLLMProviders,
    select: (rows: LLMProvider[]) => rows.filter((p) => p.is_active === 1),
  });

  // When switching to LLM mode and no provider is set, default to first active provider
  useEffect(() => {
    if (
      isOpen &&
      (values.provenance_mode === "llm" || values.use_llm_judge) &&
      !values.llm_provider_id &&
      providers.length > 0
    ) {
      setValues((prev) => ({
        ...prev,
        llm_provider_id: providers[0].id,
      }));
    }
  }, [isOpen, values.provenance_mode, values.use_llm_judge, values.llm_provider_id, providers, setValues]);

  return (
    <NodeConfigPanel
      {...props}
      data={merged}
      footer={
        <div className="flex justify-end gap-2">
          <button
            type="button"
            className="px-3 py-1.5 text-sm border rounded-md"
            onClick={onClose}
          >
            Cancel
          </button>
          <button
            type="button"
            className="px-3 py-1.5 text-sm bg-primary text-primary-foreground rounded-md"
            onClick={handleSave}
          >
            Save Changes
          </button>
        </div>
      }
    >
      <div className="space-y-4">
        <div className="space-y-2">
          <Label>Answer field key</Label>
          <DraggableTextArea
            value={values.answer_field ?? "answer"}
            onChange={(e) => setField("answer_field", e.target.value)}
            placeholder="answer"
            size="hint"
          />
        </div>
        <div className="space-y-2">
          <Label>Context field key</Label>
          <DraggableTextArea
            value={values.context_field ?? "context"}
            onChange={(e) => setField("context_field", e.target.value)}
            placeholder="context"
            size="hint"
          />
        </div>
        <div className="space-y-2">
          <Label>Minimum provenance score (0-1)</Label>
          <RichInput
            type="number"
            step="0.01"
            min={0}
            max={1}
            value={values.min_score ?? 0.5}
            onChange={(e) => setField("min_score", Number(e.target.value))}
          />
        </div>
        {false && (
          <div className="flex items-center justify-between">
            <div className="space-y-1">
              <Label>Fail on violation</Label>
              <p className="text-xs text-muted-foreground">
                When enabled, blocks the workflow branch if the provenance score is below the threshold.
              </p>
            </div>
            <Switch
              checked={values.fail_on_violation ?? false}
              onCheckedChange={(checked) =>
                setField("fail_on_violation", checked)
              }
            />
          </div>
        )}
        <div className="flex items-center justify-between">
          <div className="space-y-1">
            <Label>Fallback answer on violation</Label>
            <p className="text-xs text-muted-foreground">
              When enabled, substitutes the answer with the fallback text instead of blocking.
            </p>
          </div>
          <Switch
            checked={values.fallback_answer_enabled ?? false}
            onCheckedChange={(checked) =>
              setField("fallback_answer_enabled", checked)
            }
          />
        </div>
        {values.fallback_answer_enabled && (
          <div className="space-y-2">
            <Label>Fallback answer text</Label>
            <DraggableTextArea
              value={values.fallback_answer ?? ""}
              onChange={(e) => setField("fallback_answer", e.target.value)}
              placeholder="e.g. I'm sorry, I cannot provide an answer based on the available information."
              size="hint"
            />
          </div>
        )}

        <div className="space-y-2 pt-2 border-t border-border">
          <Label>Provenance mode</Label>
          <Select
            value={values.provenance_mode || "embeddings"}
            onValueChange={(value: "embeddings" | "llm") =>
              setValues((prev) => ({
                ...prev,
                provenance_mode: value,
                use_llm_judge: value === "llm",
              }))
            }
          >
            <SelectTrigger className="w-full">
              <SelectValue placeholder="Select mode" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="embeddings">
                Provenance (Embeddings)
              </SelectItem>
              <SelectItem value="llm">Provenance (LLM judge)</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {values.provenance_mode === "embeddings" && (
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>Embedding provider</Label>
              <Select
                value={values.embedding_type || "huggingface"}
                onValueChange={(
                  value: "openai" | "huggingface" | "bedrock",
                ) => setField("embedding_type", value)}
              >
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="Select provider" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="huggingface">HuggingFace</SelectItem>
                  <SelectItem value="openai">OpenAI</SelectItem>
                  <SelectItem value="bedrock">AWS Bedrock</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Embedding model name</Label>
              <RichInput
                value={values.embedding_model_name ?? ""}
                onChange={(e) =>
                  setField("embedding_model_name", e.target.value)
                }
                placeholder="e.g. all-MiniLM-L6-v2"
              />
            </div>
          </div>
        )}

        {values.provenance_mode === "llm" && (
          <div className="space-y-4">
            <div className="space-y-1">
              <Label>LLM as judge</Label>
              <p className="text-xs text-muted-foreground">
                Uses an LLM provider to judge whether the answer is supported
                by the context.
              </p>
            </div>
            <div className="space-y-2">
              <Label>LLM Provider</Label>
              <Select
                value={values.llm_provider_id || ""}
                onValueChange={(val) => setField("llm_provider_id", val)}
              >
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="Select provider" />
                </SelectTrigger>
                <SelectContent>
                  {providers.map((provider) => (
                    <SelectItem key={provider.id} value={provider.id}>
                      {provider.name} ({provider.llm_model_provider} -{" "}
                      {provider.llm_model})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label>Additional judge instructions</Label>
                {workflow?.id && props.nodeId && (
                  <PromptEditorButton
                    workflowId={workflow.id}
                    nodeId={props.nodeId}
                    promptField="llm_judge_system_prompt_suffix"
                    currentValue={values.llm_judge_system_prompt_suffix ?? ""}
                    onPromptChange={(val) =>
                      setField("llm_judge_system_prompt_suffix", val)
                    }
                    defaultProviderId={values.llm_provider_id}
                  />
                )}
              </div>
              <p className="text-xs text-muted-foreground">
                Appended to the base system prompt to fine-tune judge behaviour.
                E.g. <em>"When no Context is available, treat the answer as supported."</em>
              </p>
              <DraggableTextArea
                value={values.llm_judge_system_prompt_suffix ?? ""}
                onChange={(e) =>
                  setField("llm_judge_system_prompt_suffix", e.target.value)
                }
                placeholder="Optional extra instructions for the judge..."
                rows={4}
              />
            </div>
          </div>
        )}
      </div>
    </NodeConfigPanel>
  );
};

