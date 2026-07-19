import React, { useEffect, useState } from "react";
import toast from "react-hot-toast";
import { BaseLLMNodeData, SubAgentNodeData } from "../types/nodes";
import { Button } from "@/components/button";
import { Label } from "@/components/label";
import { Textarea } from "@/components/ui/textarea";
import { RichInput } from "@/components/richInput";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/select";
import { ModelConfiguration } from "../components/ModelConfiguration";
import { NodeConfigPanel } from "../components/NodeConfigPanel";
import { BaseNodeDialogProps } from "./base";

type SubAgentDialogProps = BaseNodeDialogProps<SubAgentNodeData, SubAgentNodeData>;

const MODE_HELP: Record<SubAgentNodeData["mode"], string> = {
  single_turn: "Answers once and returns to the parent automatically. No clarifying questions.",
  task: "Does a bounded job. May ask the user one clarifying question, then calls finish_task.",
  chat: "Takes over the conversation and owns turns until it hands control back to the parent.",
};

export const SubAgentDialog: React.FC<SubAgentDialogProps> = (props) => {
  const { isOpen, onClose, data, onUpdate } = props;

  const [config, setConfig] = useState<SubAgentNodeData>(data);

  useEffect(() => {
    if (isOpen) {
      setConfig(data);
    }
  }, [isOpen, data]);

  // ModelConfiguration edits the shared LLM fields
  const handleModelConfigChange = (updated: BaseLLMNodeData) => {
    setConfig((prev) => ({ ...prev, ...updated }) as SubAgentNodeData);
  };

  const handleSave = () => {
    const name = (config.name || "").trim();
    const description = (config.description || "").trim();
    if (!config.providerId) {
      toast.error("Select an LLM provider for the sub-agent.");
      return;
    }
    if (!description) {
      toast.error("Add a description so the parent agent knows when to delegate.");
      return;
    }
    const timeout = Number(config.timeoutSeconds ?? 120);
    if (!Number.isFinite(timeout) || timeout < 5 || timeout > 300) {
      toast.error("Timeout must be between 5 and 300 seconds.");
      return;
    }

    onUpdate({
      ...data,
      ...config,
      name,
      description,
      timeoutSeconds: timeout,
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
          <Button onClick={handleSave}>Save Changes</Button>
        </>
      }
      {...props}
      data={{
        ...data,
        ...config,
      }}
    >
      <div className="space-y-2">
        <Label htmlFor="sub-agent-mode">Collaboration Mode</Label>
        <Select
          value={config.mode}
          onValueChange={(mode) =>
            setConfig((prev) => ({ ...prev, mode: mode as SubAgentNodeData["mode"] }))
          }
        >
          <SelectTrigger id="sub-agent-mode" className="w-full">
            <SelectValue placeholder="Select a mode" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="single_turn">Single Turn</SelectItem>
            <SelectItem value="task">Task</SelectItem>
            <SelectItem value="chat">Chat</SelectItem>
          </SelectContent>
        </Select>
        <p className="text-xs text-muted-foreground">{MODE_HELP[config.mode]}</p>
      </div>

      <div className="space-y-2">
        <Label htmlFor="sub-agent-description">Delegation Description</Label>
        <Textarea
          id="sub-agent-description"
          value={config.description || ""}
          onChange={(e) =>
            setConfig((prev) => ({ ...prev, description: e.target.value }))
          }
          placeholder="What this sub-agent handles, e.g. searches flights and checks fares"
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="sub-agent-timeout">Timeout (seconds)</Label>
        <RichInput
          id="sub-agent-timeout"
          type="number"
          min={5}
          max={300}
          step={5}
          value={config.timeoutSeconds ?? 120}
          onChange={(e) =>
            setConfig((prev) => ({
              ...prev,
              timeoutSeconds: parseInt(e.target.value) || 120,
            }))
          }
          placeholder="120"
        />
      </div>

      <ModelConfiguration
        id="sub-agent-config"
        config={config}
        onConfigChange={handleModelConfigChange}
        typeSelect="agent"
        showUserPrompt={false}
      />
    </NodeConfigPanel>
  );
};
