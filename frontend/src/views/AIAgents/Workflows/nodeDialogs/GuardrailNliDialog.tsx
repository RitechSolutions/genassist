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
import { BaseNodeDialogProps } from "./base";
import {
  GuardrailNliNodeData,
  NodeData,
} from "../types/nodes";
import { NodeConfigPanel } from "../components/NodeConfigPanel";
import { DraggableTextArea } from "../components/custom/DraggableTextArea";

type Props = BaseNodeDialogProps<
  GuardrailNliNodeData,
  GuardrailNliNodeData
>;

const NLI_MODEL_OPTIONS = [
  {
    value: "cross-encoder/nli-deberta-v3-base",
    label: "DeBERTa v3 Base (NLI)",
  },
  {
    value: "cross-encoder/nli-roberta-base",
    label: "RoBERTa Base (NLI)",
  },
];

export const GuardrailNliDialog: React.FC<Props> = (props) => {
  const { isOpen, onClose, data, onUpdate } = props;
  const [localData, setLocalData] = useState<GuardrailNliNodeData>(data);

  useEffect(() => {
    if (isOpen) {
      setLocalData(data);
    }
  }, [isOpen, data]);

  const handleSave = () => {
    onUpdate({
      ...data,
      ...localData,
    } as GuardrailNliNodeData & NodeData);
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
          <Label>Answer</Label>
          <DraggableTextArea
            value={localData.answer_field || ""}
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
          <Label>Evidence</Label>
          <DraggableTextArea
            value={localData.evidence_field || ""}
            onChange={(e) =>
              setLocalData((prev) => ({
                ...prev,
                evidence_field: e.target.value,
              }))
            }
            placeholder="context"
            rows={2}
          />
        </div>
        <div className="space-y-2">
          <Label>NLI model</Label>
          <Select
            value={
              localData.nli_model_name ||
              "cross-encoder/nli-deberta-v3-base"
            }
            onValueChange={(value) =>
              setLocalData((prev) => ({
                ...prev,
                nli_model_name: value,
              }))
            }
          >
            <SelectTrigger className="w-full">
              <SelectValue placeholder="Select NLI model" />
            </SelectTrigger>
            <SelectContent>
              {NLI_MODEL_OPTIONS.map((opt) => (
                <SelectItem key={opt.value} value={opt.value}>
                  {opt.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-2">
          <Label>Minimum entailment score (0-1)</Label>
          <Input
            type="number"
            step="0.01"
            min={0}
            max={1}
            value={localData.min_entail_score ?? 0.5}
            onChange={(e) =>
              setLocalData((prev) => ({
                ...prev,
                min_entail_score: Number(e.target.value),
              }))
            }
          />
        </div>
        <div className="flex items-center justify-between">
          <div className="space-y-1">
            <Label>Fail on contradiction</Label>
            <p className="text-xs text-muted-foreground">
              When enabled, blocks the workflow branch if the answer contradicts the evidence.
            </p>
          </div>
          <Switch
            checked={localData.fail_on_contradiction ?? false}
            onCheckedChange={(checked) =>
              setLocalData((prev) => ({
                ...prev,
                fail_on_contradiction: checked,
              }))
            }
          />
        </div>
        <div className="flex items-center justify-between">
          <div className="space-y-1">
            <Label>Fallback answer on contradiction</Label>
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
      </div>
    </NodeConfigPanel>
  );
};

