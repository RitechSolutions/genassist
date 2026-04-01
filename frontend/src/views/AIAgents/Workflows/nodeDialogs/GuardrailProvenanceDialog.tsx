import React, { useEffect, useState } from "react";
import { Input } from "@/components/input";
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
import {
  GuardrailProvenanceNodeData,
  NodeData,
} from "../types/nodes";
import { NodeConfigPanel } from "../components/NodeConfigPanel";
import { DraggableTextArea } from "../components/custom/DraggableTextArea";

type Props = BaseNodeDialogProps<
  GuardrailProvenanceNodeData,
  GuardrailProvenanceNodeData
>;

export const GuardrailProvenanceDialog: React.FC<Props> = (props) => {
  const { isOpen, onClose, data, onUpdate } = props;
  const [localData, setLocalData] = useState<GuardrailProvenanceNodeData>(data);

  const { data: providers = [] } = useQuery({
    queryKey: ["llmProviders"],
    queryFn: getAllLLMProviders,
    select: (rows: LLMProvider[]) => rows.filter((p) => p.is_active === 1),
  });

  useEffect(() => {
    if (isOpen) {
      setLocalData(data);
    }
  }, [isOpen, data]);

  // When switching to LLM mode and no provider is set, default to first active provider
  useEffect(() => {
    if (
      isOpen &&
      (localData.provenance_mode === "llm" || localData.use_llm_judge) &&
      !localData.llm_provider_id &&
      providers.length > 0
    ) {
      setLocalData((prev) => ({
        ...prev,
        llm_provider_id: providers[0].id,
      }));
    }
  }, [isOpen, localData.provenance_mode, localData.use_llm_judge, localData.llm_provider_id, providers]);

  const handleSave = () => {
    onUpdate({
      ...data,
      ...localData,
    } as GuardrailProvenanceNodeData & NodeData);
    onClose();
  };

  return (
    <NodeConfigPanel
      {...props}
      data={localData as unknown as NodeData}
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
            value={localData.answer_field ?? "answer"}
            onChange={(e) =>
              setLocalData((prev) => ({
                ...prev,
                answer_field: e.target.value,
              }))
            }
            placeholder="answer"
            rows={2}
          />
        </div>
        <div className="space-y-2">
          <Label>Context field key</Label>
          <DraggableTextArea
            value={localData.context_field ?? "context"}
            onChange={(e) =>
              setLocalData((prev) => ({
                ...prev,
                context_field: e.target.value,
              }))
            }
            placeholder="context"
            rows={2}
          />
        </div>
        <div className="space-y-2">
          <Label>Minimum provenance score (0-1)</Label>
          <Input
            type="number"
            step="0.01"
            min={0}
            max={1}
            value={localData.min_score ?? 0.5}
            onChange={(e) =>
              setLocalData((prev) => ({
                ...prev,
                min_score: Number(e.target.value),
              }))
            }
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
              checked={localData.fail_on_violation ?? false}
              onCheckedChange={(checked) =>
                setLocalData((prev) => ({
                  ...prev,
                  fail_on_violation: checked,
                }))
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
            checked={localData.fallback_answer_enabled ?? false}
            onCheckedChange={(checked) =>
              setLocalData((prev) => ({
                ...prev,
                fallback_answer_enabled: checked,
              }))
            }
          />
        </div>
        {localData.fallback_answer_enabled && (
          <div className="space-y-2">
            <Label>Fallback answer text</Label>
            <DraggableTextArea
              value={localData.fallback_answer ?? ""}
              onChange={(e) =>
                setLocalData((prev) => ({
                  ...prev,
                  fallback_answer: e.target.value,
                }))
              }
              placeholder="e.g. I'm sorry, I cannot provide an answer based on the available information."
              rows={3}
            />
          </div>
        )}

        <div className="space-y-2 pt-2 border-t border-border">
          <Label>Provenance mode</Label>
          <Select
            value={localData.provenance_mode || "embeddings"}
            onValueChange={(value: "embeddings" | "llm") =>
              setLocalData((prev) => ({
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

        {localData.provenance_mode === "embeddings" && (
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>Embedding provider</Label>
              <Select
                value={localData.embedding_type || "huggingface"}
                onValueChange={(
                  value: "openai" | "huggingface" | "bedrock",
                ) =>
                  setLocalData((prev) => ({
                    ...prev,
                    embedding_type: value,
                  }))
                }
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
              <Input
                value={localData.embedding_model_name ?? ""}
                onChange={(e) =>
                  setLocalData((prev) => ({
                    ...prev,
                    embedding_model_name: e.target.value,
                  }))
                }
                placeholder="e.g. all-MiniLM-L6-v2"
              />
            </div>
          </div>
        )}

        {localData.provenance_mode === "llm" && (
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
                value={localData.llm_provider_id || ""}
                onValueChange={(val) =>
                  setLocalData((prev) => ({
                    ...prev,
                    llm_provider_id: val,
                  }))
                }
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
              <Label>Additional judge instructions</Label>
              <p className="text-xs text-muted-foreground">
                Appended to the base system prompt to fine-tune judge behaviour.
                E.g. <em>"When no Context is available, treat the answer as supported."</em>
              </p>
              <DraggableTextArea
                value={localData.llm_judge_system_prompt_suffix ?? ""}
                onChange={(e) =>
                  setLocalData((prev) => ({
                    ...prev,
                    llm_judge_system_prompt_suffix: e.target.value,
                  }))
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

