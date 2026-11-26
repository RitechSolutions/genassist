import React from "react";
import { Save } from "lucide-react";
import { Button } from "@/components/button";
import { Label } from "@/components/label";
import { RichInput } from "@/components/richInput";
import { useToast } from "@/components/use-toast";
import {
  DEFAULT_BLOCKED_MESSAGE,
  HARM_CATEGORIES,
  guardrailLimitError,
} from "@/helpers/guardrailChecks";
import {
  GuardrailCheckSettings,
  HarmfulContent,
} from "@/interfaces/guardrails.interface";
import { GuardrailChecksEditor } from "@/views/AIAgents/components/GuardrailChecksEditor";
import { BaseNodeDialogProps } from "./base";
import { GuardrailNodeData } from "../types/nodes";
import { NodeConfigPanel } from "../components/NodeConfigPanel";
import { DraggableTextArea } from "../components/custom/DraggableTextArea";
import { useNodeDialogState } from "./useNodeDialogState";

type Props = BaseNodeDialogProps<GuardrailNodeData, GuardrailNodeData>;

const checksOf = (data: GuardrailNodeData): GuardrailCheckSettings => ({
  prompt_attack: data.prompt_attack ?? "off",
  harmful_content: Object.fromEntries(
    HARM_CATEGORIES.map(({ key }) => [key, data.harmful_content?.[key] ?? "off"])
  ) as HarmfulContent,
  denied_topics: (data.denied_topics ?? []).map((topic) => ({
    ...topic,
    examples: topic.examples ?? [],
  })),
  blocked_words: data.blocked_words ?? [],
});

export const GuardrailDialog: React.FC<Props> = (props) => {
  const { onClose, data } = props;
  const { toast } = useToast();

  const { values, setValues, setField, merged, handleSave } =
    useNodeDialogState(props, () => ({
      text: data.text ?? "",
      providerId: data.providerId ?? "",
      blocked_message: data.blocked_message ?? "",
      ...checksOf(data),
    }));

  const topicsComplete = values.denied_topics.every(
    (topic) => topic.name.trim() && topic.definition.trim()
  );
  const limitError = guardrailLimitError(values);

  const saveIfValid = () => {
    if (!topicsComplete) {
      toast({
        title: "Topic incomplete",
        description: "Give each denied topic a name and a definition.",
        variant: "destructive",
      });
      return;
    }
    if (limitError) {
      toast({
        title: "Over the limit",
        description: limitError,
        variant: "destructive",
      });
      return;
    }
    handleSave();
  };

  return (
    <NodeConfigPanel
      footer={
        <>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button
            onClick={saveIfValid}
            disabled={!topicsComplete || !!limitError}
          >
            <Save className="h-4 w-4 mr-2" />
            Save Changes
          </Button>
        </>
      }
      {...props}
      onSave={saveIfValid}
      data={merged}
    >
      <div className="space-y-2">
        <Label htmlFor="guardrail-text">Text</Label>
        <DraggableTextArea
          id="guardrail-text"
          size="hint"
          value={values.text}
          onChange={(e) => setField("text", e.target.value)}
          placeholder="{{session.message}}"
          className="w-full text-sm"
        />
        <p className="text-sm text-muted-foreground">
          The text to check, usually a variable such as {"{{session.message}}"}.
        </p>
      </div>

      <GuardrailChecksEditor
        value={values}
        onChange={(checks) => setValues((prev) => ({ ...prev, ...checks }))}
        judgeProviderId={values.providerId || null}
        onJudgeProviderChange={(providerId) => setField("providerId", providerId)}
      />

      <div className="space-y-2">
        <Label htmlFor="guardrail-blocked-message">Blocked message</Label>
        <RichInput
          id="guardrail-blocked-message"
          value={values.blocked_message}
          maxLength={500}
          onChange={(e) => setField("blocked_message", e.target.value)}
          placeholder={DEFAULT_BLOCKED_MESSAGE}
        />
        <p className="text-sm text-muted-foreground">
          Give each exit its own Chat Output. Leave Blocked unconnected to reply
          with the blocked message. To check spoken replies, put this node
          before Text to Speech. To check File Reader or knowledge base text on
          its way to an LLM Model block, put this node between them.
        </p>
      </div>
    </NodeConfigPanel>
  );
};
